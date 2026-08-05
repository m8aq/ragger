package dev.ragger.valetotems;

/**
 * How far along a totem site is, derived from that site's varbits.
 */
public enum SiteStage {

    /** Nothing built here. */
    EMPTY("Empty"),

    /** A totem stands here with at least one of its four segments still uncarved. */
    CARVING("Carving"),

    /** All four segments carved, no decorations yet. */
    CARVED("Carved"),

    /** Carved and at least one decoration applied. */
    DECORATED("Decorated");

    private final String displayName;

    SiteStage(final String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
