package dev.ragger.valetotems;

import net.runelite.client.ui.overlay.OverlayPanel;
import net.runelite.client.ui.overlay.OverlayPosition;
import net.runelite.client.ui.overlay.components.LineComponent;
import net.runelite.client.ui.overlay.components.TitleComponent;

import javax.inject.Inject;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Graphics2D;

/**
 * Side panel listing carried supplies, the suggested next site, and every site's state.
 */
public class ValeTotemsPanelOverlay extends OverlayPanel {

    private static final int PANEL_WIDTH = 210;

    private final ValeTotemsPlugin plugin;
    private final ValeTotemsConfig config;

    @Inject
    public ValeTotemsPanelOverlay(final ValeTotemsPlugin plugin, final ValeTotemsConfig config) {
        this.plugin = plugin;
        this.config = config;

        setPosition(OverlayPosition.TOP_LEFT);
        setPreferredSize(new Dimension(PANEL_WIDTH, 0));
    }

    @Override
    public Dimension render(final Graphics2D graphics) {
        if (!config.showPanel() || !plugin.isActive()) {
            return null;
        }

        panelComponent.getChildren().add(TitleComponent.builder()
            .text("Vale Totems")
            .color(Color.WHITE)
            .build());

        addSupplies();
        addRecommendation();
        addSites();

        return super.render(graphics);
    }

    private void addSupplies() {
        final WoodType wood = plugin.getCarriedWood();

        panelComponent.getChildren().add(LineComponent.builder()
            .left("Wood")
            .right(wood == null ? "none" : wood.getDisplayName())
            .build());

        panelComponent.getChildren().add(LineComponent.builder()
            .left("Logs / decor")
            .right(plugin.getCarriedLogs() + " / " + plugin.getCarriedDecorations())
            .build());

        final int boosted = plugin.getTrailXpActionsLeft();

        if (boosted > 0) {
            panelComponent.getChildren().add(LineComponent.builder()
                .left("Trail XP left")
                .right(boosted + " actions")
                .rightColor(SiteColors.ENT_BUFFED)
                .build());
        }
    }

    private void addRecommendation() {
        if (!config.suggestNextSite()) {
            return;
        }

        final TotemSite recommended = plugin.getRecommendedSite();

        panelComponent.getChildren().add(LineComponent.builder()
            .left("Go to")
            .right(recommended == null ? "-" : "site " + recommended.getNumber())
            .rightColor(Color.WHITE)
            .build());
    }

    private void addSites() {
        for (final TotemSite site : plugin.getSites()) {
            panelComponent.getChildren().add(LineComponent.builder()
                .left(String.valueOf(site.getNumber()))
                .right(describe(site))
                .rightColor(SiteColors.forSite(site))
                .build());
        }
    }

    private String describe(final TotemSite site) {
        if (site.getStage() == SiteStage.EMPTY) {
            return "empty";
        }

        final String wood = site.getWood() == null ? "" : site.getWood().getDisplayName() + " ";
        return wood + site.getCarvedSegments() + "/4c " + site.getDecorations() + "/4d " + site.getDecay() + "v";
    }
}
