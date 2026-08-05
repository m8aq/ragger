package dev.ragger.valetotems;

import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;

@ConfigGroup(ValeTotemsConfig.GROUP)
public interface ValeTotemsConfig extends Config {

    String GROUP = "valetotems";

    @ConfigItem(
        keyName = "showSites",
        name = "Highlight totem sites",
        description = "Draw a marker and status label on each of the eight totem sites",
        position = 1
    )
    default boolean showSites() {
        return true;
    }

    @ConfigItem(
        keyName = "showEnts",
        name = "Highlight ents",
        description = "Draw a marker on each ent, gold when it carries the ent trail bonus",
        position = 2
    )
    default boolean showEnts() {
        return true;
    }

    @ConfigItem(
        keyName = "showTrails",
        name = "Highlight ent trails",
        description = "Outline ent trail flowers that have not been stepped on yet",
        position = 7
    )
    default boolean showTrails() {
        return true;
    }

    @ConfigItem(
        keyName = "showMinimap",
        name = "Show on minimap",
        description = "Draw site and ent markers on the minimap",
        position = 3
    )
    default boolean showMinimap() {
        return true;
    }

    @ConfigItem(
        keyName = "showPanel",
        name = "Show info panel",
        description = "Show the panel listing site states and the suggested next site",
        position = 4
    )
    default boolean showPanel() {
        return true;
    }

    @ConfigItem(
        keyName = "suggestNextSite",
        name = "Suggest next site",
        description = "Score the sites by expected offerings against travel time and highlight the best one",
        position = 5
    )
    default boolean suggestNextSite() {
        return true;
    }

    @ConfigItem(
        keyName = "tilesPerTick",
        name = "Run speed (tiles/tick)",
        description = "Used to estimate whether you can reach a site before the ent's window closes. 2 when running",
        position = 6
    )
    default int tilesPerTick() {
        return 2;
    }
}
