package dev.ragger.cachedump;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import net.runelite.cache.ConfigType;
import net.runelite.cache.IndexType;
import net.runelite.cache.definitions.VarbitDefinition;
import net.runelite.cache.definitions.loaders.VarbitLoader;
import net.runelite.cache.fs.Archive;
import net.runelite.cache.fs.ArchiveFiles;
import net.runelite.cache.fs.FSFile;
import net.runelite.cache.fs.Index;
import net.runelite.cache.fs.Store;

import java.io.*;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.jar.JarFile;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;

/**
 * Dumps game variable constants from RuneLite API classes to JSON.
 *
 * Uses reflection to extract public static final int fields and parses
 * source JARs for Javadoc comments where available.
 *
 * Output format:
 * {
 *   "var_type": "varp",
 *   "entries": [
 *     { "name": "COM_STANCE", "id": 46, "comment": "..." },
 *     ...
 *   ]
 * }
 */
public class DumpGameVars {

    private static final Map<String, VarSource> SOURCES = new LinkedHashMap<>();

    static {
        SOURCES.put("varp", new VarSource(
                "net.runelite.api.gameval.VarPlayerID",
                "net/runelite/api/gameval/VarPlayerID.java"
        ));
        SOURCES.put("varbit", new VarSource(
                "net.runelite.api.gameval.VarbitID",
                "net/runelite/api/gameval/VarbitID.java"
        ));
        SOURCES.put("varc_int", new VarSource(
                "net.runelite.api.gameval.VarClientID",
                "net/runelite/api/gameval/VarClientID.java"
        ));
    }

    record VarSource(String className, String sourcePath) {}

    /** varp/lsb/msb/bits are cache varbit structure fields, present only for var_type "varbit". */
    record VarEntry(String name, int id, String comment, Integer varp, Integer lsb, Integer msb, Integer bits) {}

    record VarFile(String var_type, List<VarEntry> entries) {}

    public static void main(String[] args) throws Exception {
        String output = "../../data/game-vars";
        String cachePath = null;

        for (int i = 0; i < args.length; i++) {
            if ("--output".equals(args[i]) && i + 1 < args.length) {
                output = args[++i];
            } else if ("--cache".equals(args[i]) && i + 1 < args.length) {
                cachePath = args[++i];
            }
        }

        Path outputDir = Path.of(output);
        Files.createDirectories(outputDir);

        // Find the sources JAR on the classpath for comment extraction
        Map<String, Map<String, String>> allComments = findAndParseSourceJars();
        Map<Integer, VarbitDefinition> varbitStructures = loadVarbitStructures(cachePath);

        Gson gson = new GsonBuilder().setPrettyPrinting().create();

        for (var entry : SOURCES.entrySet()) {
            String varType = entry.getKey();
            VarSource source = entry.getValue();

            Class<?> clazz = Class.forName(source.className());
            Map<String, String> comments = allComments.getOrDefault(source.sourcePath(), Map.of());

            List<VarEntry> entries = new ArrayList<>();
            for (Field field : clazz.getDeclaredFields()) {
                if (isConstant(field)) {
                    String name = field.getName();
                    int id = field.getInt(null);
                    String comment = comments.get(name);
                    VarbitDefinition structure = "varbit".equals(varType) ? varbitStructures.get(id) : null;

                    if (structure == null) {
                        entries.add(new VarEntry(name, id, comment, null, null, null, null));
                    } else {
                        int lsb = structure.getLeastSignificantBit();
                        int msb = structure.getMostSignificantBit();
                        entries.add(new VarEntry(name, id, comment, structure.getIndex(), lsb, msb, msb - lsb + 1));
                    }
                }
            }

            entries.sort(Comparator.comparingInt(VarEntry::id).thenComparing(VarEntry::name));

            VarFile varFile = new VarFile(varType, entries);
            Path outPath = outputDir.resolve(varType + ".json");
            try (Writer writer = Files.newBufferedWriter(outPath)) {
                gson.toJson(varFile, writer);
            }

            System.out.printf("%s: %d entries -> %s%n", varType, entries.size(), outPath);
        }
    }

    /**
     * Load varbit structures (parent varp, bit range) from the game cache's varbit config archive.
     * Keyed by varbit ID.
     */
    private static Map<Integer, VarbitDefinition> loadVarbitStructures(String cachePath) throws Exception {
        File cacheDir = CacheLoader.resolveCache(cachePath, Path.of("../../data/cache-dump"));
        Map<Integer, VarbitDefinition> structures = new HashMap<>();
        VarbitLoader loader = new VarbitLoader();

        try (Store store = new Store(cacheDir)) {
            store.load();

            Index configs = store.getIndex(IndexType.CONFIGS);
            Archive archive = configs.getArchive(ConfigType.VARBIT.getId());
            byte[] archiveData = store.getStorage().loadArchive(archive);
            ArchiveFiles files = archive.getFiles(archiveData);

            for (FSFile file : files.getFiles()) {
                VarbitDefinition def = loader.load(file.getFileId(), file.getContents());
                structures.put(def.getId(), def);
            }
        }

        System.out.printf("Loaded %d varbit structures from cache%n", structures.size());
        return structures;
    }

    private static boolean isConstant(Field field) {
        int mods = field.getModifiers();
        return Modifier.isPublic(mods)
                && Modifier.isStatic(mods)
                && Modifier.isFinal(mods)
                && field.getType() == int.class;
    }

    /**
     * Search the classpath for source JARs and parse Javadoc comments from them.
     */
    private static Map<String, Map<String, String>> findAndParseSourceJars() {
        Map<String, Map<String, String>> result = new HashMap<>();
        String classpath = System.getProperty("java.class.path", "");

        for (String entry : classpath.split(File.pathSeparator)) {
            if (!entry.endsWith("-sources.jar")) continue;

            try (JarFile jar = new JarFile(entry)) {
                for (var source : SOURCES.values()) {
                    ZipEntry ze = jar.getEntry(source.sourcePath());
                    if (ze == null) continue;

                    try (InputStream is = jar.getInputStream(ze)) {
                        String sourceCode = new String(is.readAllBytes());
                        result.put(source.sourcePath(), parseFieldComments(sourceCode));
                    }
                }
            } catch (IOException e) {
                // skip unreadable JARs
            }
        }

        return result;
    }

    /**
     * Parse Javadoc and single/multi-line comments preceding field declarations.
     * Returns a map of field name -> comment text.
     */
    private static Map<String, String> parseFieldComments(String source) {
        Map<String, String> comments = new HashMap<>();

        // Match Javadoc (/** ... */) or block comments (/* ... */) followed by a field
        Pattern pattern = Pattern.compile(
                "/\\*\\*?\\s*(.*?)\\s*\\*/\\s*" +
                "public\\s+static\\s+final\\s+int\\s+(\\w+)",
                Pattern.DOTALL
        );

        Matcher matcher = pattern.matcher(source);
        while (matcher.find()) {
            String rawComment = matcher.group(1);
            String fieldName = matcher.group(2);

            // Clean up the comment: strip leading * and whitespace
            String cleaned = rawComment
                    .replaceAll("(?m)^\\s*\\*\\s?", "")  // strip leading * on each line
                    .replaceAll("\\s+", " ")              // collapse whitespace
                    .strip();

            if (!cleaned.isEmpty()) {
                comments.put(fieldName, cleaned);
            }
        }

        // Also match single-line comments: // comment \n field
        Pattern singleLine = Pattern.compile(
                "//\\s*(.+?)\\s*\\n\\s*public\\s+static\\s+final\\s+int\\s+(\\w+)"
        );
        Matcher slMatcher = singleLine.matcher(source);
        while (slMatcher.find()) {
            String comment = slMatcher.group(1).strip();
            String fieldName = slMatcher.group(2);
            if (!comment.isEmpty()) {
                comments.putIfAbsent(fieldName, comment);
            }
        }

        return comments;
    }
}
