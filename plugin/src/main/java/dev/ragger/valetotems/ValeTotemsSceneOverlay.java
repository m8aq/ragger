package dev.ragger.valetotems;

import net.runelite.api.Client;
import net.runelite.api.GameObject;
import net.runelite.api.NPC;
import net.runelite.api.Perspective;
import net.runelite.api.Point;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;
import net.runelite.client.ui.overlay.OverlayUtil;

import javax.inject.Inject;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Graphics2D;
import java.awt.Polygon;
import java.awt.Shape;
import java.util.List;

/**
 * Draws totem site markers and ent markers on the game viewport.
 */
public class ValeTotemsSceneOverlay extends Overlay {

    private final Client client;
    private final ValeTotemsPlugin plugin;
    private final ValeTotemsConfig config;

    @Inject
    public ValeTotemsSceneOverlay(final Client client, final ValeTotemsPlugin plugin, final ValeTotemsConfig config) {
        this.client = client;
        this.plugin = plugin;
        this.config = config;

        setPosition(OverlayPosition.DYNAMIC);
        setLayer(OverlayLayer.ABOVE_SCENE);
    }

    @Override
    public Dimension render(final Graphics2D graphics) {
        if (!plugin.isActive()) {
            return null;
        }

        if (config.showSites()) {
            renderSites(graphics);
        }

        if (config.showEnts()) {
            renderEnts(graphics);
        }

        if (config.showTrails()) {
            renderTrails(graphics);
        }

        return null;
    }

    private void renderTrails(final Graphics2D graphics) {
        for (final GameObject trail : plugin.getInactiveTrails()) {
            final Shape clickbox = trail.getClickbox();

            if (clickbox != null) {
                OverlayUtil.renderPolygon(graphics, clickbox, SiteColors.ENT_BUFFED);
            }
        }
    }

    private void renderSites(final Graphics2D graphics) {
        final TotemSite recommended = plugin.getRecommendedSite();

        for (final TotemSite site : plugin.getSites()) {
            if (!site.hasPoint()) {
                continue;
            }

            final Polygon poly = tilePoly(site.getPoint());

            if (poly == null) {
                continue;
            }

            final boolean isRecommended = recommended != null && recommended.getNumber() == site.getNumber();
            final boolean hasWrongCarving = !site.getWrongCarvings().isEmpty();

            Color color = isRecommended ? SiteColors.RECOMMENDED : SiteColors.forSite(site);

            if (hasWrongCarving) {
                color = SiteColors.EMPTY;
            }

            OverlayUtil.renderPolygon(graphics, poly, color);

            final String label = label(site);
            final Point text = textPoint(graphics, site.getPoint(), label);

            if (text != null) {
                OverlayUtil.renderTextLocation(graphics, text, label, color);
            }
        }
    }

    private void renderEnts(final Graphics2D graphics) {
        for (final TrackedEnt ent : plugin.getEnts()) {
            final NPC npc = ent.getNpc();
            final Color color = ent.isBuffed() ? SiteColors.ENT_BUFFED : SiteColors.ENT;
            final Shape hull = npc.getConvexHull();

            if (hull != null) {
                OverlayUtil.renderPolygon(graphics, hull, color);
            }

            final String label = entLabel(ent);
            final Point text = npc.getCanvasTextLocation(graphics, label, 60);

            if (text != null) {
                OverlayUtil.renderTextLocation(graphics, text, label, color);
            }
        }
    }

    private String entLabel(final TrackedEnt ent) {
        final String prefix = ent.isBuffed() ? "Buffed ent" : "Ent";
        final int next = ent.nextSiteNumber();

        if (next == 0) {
            return prefix;
        }

        final int admire = ent.ticksLeftInAdmireWindow(plugin.getTick());

        if (admire > 0) {
            return prefix + " admiring, " + admire + "t to decorate";
        }

        final int ticks = ent.ticksToNextSite(plugin.getTick());

        if (ticks < 0) {
            return prefix + " -> site " + next;
        }

        return prefix + " -> site " + next + " in ~" + ticks + "t";
    }

    private String label(final TotemSite site) {
        final StringBuilder text = new StringBuilder();
        text.append(site.getNumber()).append(": ");

        if (site.getStage() == SiteStage.EMPTY) {
            text.append("empty");
            appendSpirits(text, " — carve ", site.getActiveSpirits());
            return text.toString();
        }

        if (site.getWood() != null) {
            text.append(site.getWood().getDisplayName()).append(' ');
        }

        text.append(site.getCarvedSegments()).append("/4 carved, ")
            .append(site.getDecorations()).append("/4 dec");

        if (site.getStage() == SiteStage.CARVING) {
            appendSpirits(text, " — carve ", site.getSpiritsToCarve());
        }

        appendSpirits(text, " — WRONG: ", site.getWrongCarvings());

        if (site.getDecay() > 0) {
            text.append(", ").append(site.getDecay()).append(" durability");
        }

        if (site.isOfferingsCapped()) {
            text.append(", offerings FULL");
        } else if (site.getOfferings() > 0) {
            text.append(", ").append(site.getOfferings()).append(" offerings");
        }

        return text.toString();
    }

    private void appendSpirits(final StringBuilder text, final String prefix, final List<Spirit> spirits) {
        if (spirits.isEmpty()) {
            return;
        }

        text.append(prefix);

        for (int i = 0; i < spirits.size(); i++) {
            if (i > 0) {
                text.append('/');
            }

            text.append(spirits.get(i).getDisplayName());
        }
    }

    private Polygon tilePoly(final WorldPoint point) {
        final LocalPoint local = LocalPoint.fromWorld(client.getTopLevelWorldView(), point);
        return local == null ? null : Perspective.getCanvasTilePoly(client, local);
    }

    private Point textPoint(final Graphics2D graphics, final WorldPoint point, final String text) {
        final LocalPoint local = LocalPoint.fromWorld(client.getTopLevelWorldView(), point);
        return local == null ? null : Perspective.getCanvasTextLocation(client, graphics, local, text, 0);
    }
}
