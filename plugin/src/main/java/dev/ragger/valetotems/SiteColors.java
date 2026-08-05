package dev.ragger.valetotems;

import java.awt.Color;

/**
 * Shared colours so the viewport, minimap and panel agree on what each site state looks like.
 */
public final class SiteColors {

    public static final Color EMPTY = new Color(255, 96, 96);
    public static final Color CARVING = new Color(255, 200, 64);
    public static final Color CARVED = new Color(120, 190, 255);
    public static final Color COMPLETE = new Color(96, 220, 120);
    public static final Color RECOMMENDED = Color.WHITE;
    public static final Color ENT = new Color(150, 220, 150);
    public static final Color ENT_BUFFED = new Color(255, 215, 0);

    private SiteColors() {
    }

    public static Color forSite(final TotemSite site) {
        if (site.isComplete()) {
            return COMPLETE;
        }

        return switch (site.getStage()) {
            case EMPTY -> EMPTY;
            case CARVING -> CARVING;
            case CARVED, DECORATED -> CARVED;
        };
    }
}
