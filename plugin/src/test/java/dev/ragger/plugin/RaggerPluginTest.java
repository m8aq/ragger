package dev.ragger.plugin;

import dev.ragger.valetotems.ValeTotemsPlugin;
import net.runelite.client.RuneLite;
import net.runelite.client.externalplugins.ExternalPluginManager;

public class RaggerPluginTest {
    public static void main(String[] args) throws Exception {
        ExternalPluginManager.loadBuiltin(RaggerPlugin.class, ValeTotemsPlugin.class);
        RuneLite.main(args);
    }
}
