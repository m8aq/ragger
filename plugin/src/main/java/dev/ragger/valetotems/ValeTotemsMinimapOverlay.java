package dev.ragger.valetotems;

import net.runelite.api.Client;
import net.runelite.api.Perspective;
import net.runelite.api.Point;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;

import javax.inject.Inject;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Graphics2D;

/**
 * Draws site and ent dots on the minimap.
 */
public class ValeTotemsMinimapOverlay extends Overlay {

    private static final int SITE_DOT = 6;
    private static final int ENT_DOT = 5;

    private final Client client;
    private final ValeTotemsPlugin plugin;
    private final ValeTotemsConfig config;

    @Inject
    public ValeTotemsMinimapOverlay(final Client client, final ValeTotemsPlugin plugin, final ValeTotemsConfig config) {
        this.client = client;
        this.plugin = plugin;
        this.config = config;

        setPosition(OverlayPosition.DYNAMIC);
        setLayer(OverlayLayer.ABOVE_WIDGETS);
    }

    @Override
    public Dimension render(final Graphics2D graphics) {
        if (!config.showMinimap() || !plugin.isActive()) {
            return null;
        }

        final TotemSite recommended = plugin.getRecommendedSite();

        for (final TotemSite site : plugin.getSites()) {
            if (!site.hasPoint()) {
                continue;
            }

            final boolean isRecommended = recommended != null && recommended.getNumber() == site.getNumber();
            final Color color = isRecommended ? SiteColors.RECOMMENDED : SiteColors.forSite(site);

            drawDot(graphics, site.getPoint(), color, SITE_DOT);
        }

        for (final TrackedEnt ent : plugin.getEnts()) {
            final Color color = ent.isBuffed() ? SiteColors.ENT_BUFFED : SiteColors.ENT;
            drawDot(graphics, ent.getNpc().getWorldLocation(), color, ENT_DOT);
        }

        return null;
    }

    private void drawDot(final Graphics2D graphics, final WorldPoint point, final Color color, final int size) {
        if (point == null) {
            return;
        }

        final LocalPoint local = LocalPoint.fromWorld(client.getTopLevelWorldView(), point);

        if (local == null) {
            return;
        }

        final Point minimap = Perspective.localToMinimap(client, local);

        if (minimap == null) {
            return;
        }

        final int x = minimap.getX() - size / 2;
        final int y = minimap.getY() - size / 2;

        graphics.setColor(color);
        graphics.fillOval(x, y, size, size);
        graphics.setColor(Color.BLACK);
        graphics.drawOval(x, y, size, size);
    }
}
