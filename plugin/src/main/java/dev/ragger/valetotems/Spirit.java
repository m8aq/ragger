package dev.ragger.valetotems;

/**
 * The five animal spirits, in varbit value order 1-5. A carved segment varbit stores the spirit's
 * value plus 9 (so 10-14). Value mapping taken from quest-helper's ValeTotems steps.
 */
public enum Spirit {

    BUFFALO("Buffalo"),
    JAGUAR("Jaguar"),
    EAGLE("Eagle"),
    SNAKE("Snake"),
    SCORPION("Scorpion");

    /** Carved segment varbits store the spirit value offset by this much. */
    private static final int SEGMENT_OFFSET = 9;

    private final String displayName;

    Spirit(final String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }

    /** The spirit with this varbit value 1-5, or null for 0/unknown. */
    public static Spirit fromValue(final int value) {
        if (value < 1 || value > values().length) {
            return null;
        }

        return values()[value - 1];
    }

    /** The spirit carved into a segment varbit holding {@code value}, or null if not yet carved. */
    public static Spirit fromSegmentValue(final int value) {
        return fromValue(value - SEGMENT_OFFSET);
    }
}
