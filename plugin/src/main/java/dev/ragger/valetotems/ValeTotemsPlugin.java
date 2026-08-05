package dev.ragger.valetotems;

import com.google.inject.Provides;
import net.runelite.api.Client;
import net.runelite.api.GameObject;
import net.runelite.api.GameState;
import net.runelite.api.Item;
import net.runelite.api.ItemContainer;
import net.runelite.api.NPC;
import net.runelite.api.Player;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.GameObjectDespawned;
import net.runelite.api.events.GameObjectSpawned;
import net.runelite.api.events.GameStateChanged;
import net.runelite.api.events.GameTick;
import net.runelite.api.events.ItemContainerChanged;
import net.runelite.api.events.NpcDespawned;
import net.runelite.api.events.NpcSpawned;
import net.runelite.api.gameval.InventoryID;
import net.runelite.api.gameval.VarbitID;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.game.ItemManager;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.ui.overlay.OverlayManager;

import javax.inject.Inject;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@PluginDescriptor(
    name = "Vale Totems",
    description = "Tracks totem sites, ent arrivals and offerings during the Vale Totems minigame",
    tags = {"vale", "totems", "fletching", "varlamore", "minigame"}
)
public class ValeTotemsPlugin extends Plugin {

    /** Bounding box of the Auburn Valley, used to keep the plugin idle everywhere else. */
    private static final int VALLEY_MIN_X = 1320;
    private static final int VALLEY_MAX_X = 1510;
    private static final int VALLEY_MIN_Y = 3250;
    private static final int VALLEY_MAX_Y = 3400;

    /** How close an ent must be to a site tile to count as visiting that site. */
    private static final int SITE_RADIUS = 6;

    @Inject
    private Client client;

    @Inject
    private OverlayManager overlayManager;

    @Inject
    private ItemManager itemManager;

    @Inject
    private ValeTotemsConfig config;

    @Inject
    private ValeTotemsSceneOverlay sceneOverlay;

    @Inject
    private ValeTotemsMinimapOverlay minimapOverlay;

    @Inject
    private ValeTotemsPanelOverlay panelOverlay;

    private final List<TotemSite> sites = TotemSite.buildAll();
    private final Map<Integer, TrackedEnt> entsByIndex = new HashMap<>();
    private final EntTrailTracker trails = new EntTrailTracker();

    private int tick;
    private TotemSite recommendedSite;
    private WoodType carriedWood;
    private int carriedLogs;
    private int carriedDecorations;
    private int trailXpActionsLeft;

    @Provides
    ValeTotemsConfig provideConfig(final ConfigManager configManager) {
        return configManager.getConfig(ValeTotemsConfig.class);
    }

    @Override
    protected void startUp() {
        overlayManager.add(sceneOverlay);
        overlayManager.add(minimapOverlay);
        overlayManager.add(panelOverlay);
    }

    @Override
    protected void shutDown() {
        overlayManager.remove(sceneOverlay);
        overlayManager.remove(minimapOverlay);
        overlayManager.remove(panelOverlay);

        entsByIndex.clear();
        trails.clear();
        recommendedSite = null;
    }

    @Subscribe
    public void onGameStateChanged(final GameStateChanged event) {
        if (event.getGameState() == GameState.LOADING) {
            trails.clear();
        }
    }

    @Subscribe
    public void onGameTick(final GameTick event) {
        tick++;

        if (!inValley()) {
            recommendedSite = null;
            return;
        }

        readSiteVarbits();
        trailXpActionsLeft = client.getVarbitValue(VarbitID.ENT_TOTEMS_TRAIL_XP_BUFF_ACTIONS);
        updateEnts();
        recommendedSite = config.suggestNextSite() ? chooseNextSite() : null;
    }

    @Subscribe
    public void onGameObjectSpawned(final GameObjectSpawned event) {
        final GameObject object = event.getGameObject();

        trails.add(object);

        final int siteNumber = SiteObjects.siteOfBaseObject(object.getId());

        if (siteNumber > 0) {
            sites.get(siteNumber - 1).setPoint(object.getWorldLocation());
        }
    }

    @Subscribe
    public void onGameObjectDespawned(final GameObjectDespawned event) {
        trails.remove(event.getGameObject());
    }

    @Subscribe
    public void onNpcSpawned(final NpcSpawned event) {
        final NPC npc = event.getNpc();

        if (TrackedEnt.isEnt(npc.getId())) {
            entsByIndex.put(npc.getIndex(), new TrackedEnt(npc));
        }
    }

    @Subscribe
    public void onNpcDespawned(final NpcDespawned event) {
        entsByIndex.remove(event.getNpc().getIndex());
    }

    @Subscribe
    public void onItemContainerChanged(final ItemContainerChanged event) {
        if (event.getContainerId() != InventoryID.INV) {
            return;
        }

        updateCarriedSupplies(event.getItemContainer());
    }

    private void readSiteVarbits() {
        for (final TotemSite site : sites) {
            final int number = site.getNumber();

            site.setBase(client.getVarbitValue(SiteVarbits.base(number)));
            site.setBaseCarved(client.getVarbitValue(SiteVarbits.baseCarved(number)) == 1);
            site.setSegments(
                client.getVarbitValue(SiteVarbits.low(number)),
                client.getVarbitValue(SiteVarbits.mid(number)),
                client.getVarbitValue(SiteVarbits.top(number))
            );
            site.setDecorations(client.getVarbitValue(SiteVarbits.decorations(number)));
            site.setDecay(client.getVarbitValue(SiteVarbits.decay(number)));
            site.setOfferings(client.getVarbitValue(SiteVarbits.points(number)));
            site.setTrailBuffActive(client.getVarbitValue(SiteVarbits.trailBuff(number)) > 0);
            site.setSpirits(
                client.getVarbitValue(SiteVarbits.animal1(number)),
                client.getVarbitValue(SiteVarbits.animal2(number)),
                client.getVarbitValue(SiteVarbits.animal3(number))
            );
        }
    }

    private void updateCarriedSupplies(final ItemContainer container) {
        carriedWood = null;
        carriedLogs = 0;
        carriedDecorations = 0;

        if (container == null) {
            return;
        }

        for (final Item item : container.getItems()) {
            if (item == null || item.getId() < 0) {
                continue;
            }

            final String name = itemName(item.getId());

            if (name == null) {
                continue;
            }

            final WoodType wood = WoodType.fromName(name);

            if (wood == null) {
                continue;
            }

            if (name.toLowerCase().contains("logs")) {
                carriedWood = wood;
                carriedLogs += item.getQuantity();
            } else {
                carriedDecorations += item.getQuantity();
            }
        }
    }

    private void updateEnts() {
        for (final TrackedEnt ent : entsByIndex.values()) {
            final TotemSite site = siteAt(ent.getNpc().getWorldLocation());

            if (site == null) {
                ent.leaveSite();
                continue;
            }

            ent.arriveAt(site.getNumber(), tick);
        }
    }

    /**
     * Picks the site with the best expected offerings per tick of travel, skipping any site whose
     * ent will have finished admiring before you could arrive.
     */
    private TotemSite chooseNextSite() {
        final WorldPoint player = playerLocation();

        if (player == null) {
            return null;
        }

        TotemSite best = null;
        double bestScore = 0;

        for (final TotemSite site : sites) {
            if (!site.needsWork() || !site.hasPoint()) {
                continue;
            }

            final WoodType wood = site.getWood() != null ? site.getWood() : carriedWood;

            if (wood == null) {
                continue;
            }

            final int gain = wood.offeringsFor(4) - site.offeringsPerVisit();

            if (gain <= 0) {
                continue;
            }

            final int travelTicks = Math.max(1, player.distanceTo(site.getPoint()) / Math.max(1, config.tilesPerTick()));
            final TrackedEnt inbound = entHeadingTo(site.getNumber());

            double weighted = gain;

            if (inbound != null) {
                final int arrivalTicks = inbound.ticksToNextSite(tick);

                if (arrivalTicks >= 0 && travelTicks > arrivalTicks + TrackedEnt.ADMIRE_TICKS) {
                    continue;
                }

                if (inbound.isBuffed() || site.isTrailBuffActive()) {
                    weighted *= 2;
                }
            }

            final double score = weighted / travelTicks;

            if (score > bestScore) {
                bestScore = score;
                best = site;
            }
        }

        return best;
    }

    public TrackedEnt entHeadingTo(final int siteNumber) {
        for (final TrackedEnt ent : entsByIndex.values()) {
            if (ent.nextSiteNumber() == siteNumber) {
                return ent;
            }
        }

        return null;
    }

    private TotemSite siteAt(final WorldPoint point) {
        if (point == null || point.getPlane() != TotemSite.PLANE) {
            return null;
        }

        for (final TotemSite site : sites) {
            if (site.hasPoint() && site.getPoint().distanceTo(point) <= SITE_RADIUS) {
                return site;
            }
        }

        return null;
    }

    private String itemName(final int itemId) {
        final var composition = itemManager.getItemComposition(itemId);
        return composition == null ? null : composition.getName();
    }

    private WorldPoint playerLocation() {
        final Player player = client.getLocalPlayer();
        return player == null ? null : player.getWorldLocation();
    }

    private boolean inValley() {
        final WorldPoint player = playerLocation();

        if (player == null || player.getPlane() != TotemSite.PLANE) {
            return false;
        }

        return player.getX() >= VALLEY_MIN_X && player.getX() <= VALLEY_MAX_X
            && player.getY() >= VALLEY_MIN_Y && player.getY() <= VALLEY_MAX_Y;
    }

    public List<TotemSite> getSites() {
        return sites;
    }

    public List<TrackedEnt> getEnts() {
        return new ArrayList<>(entsByIndex.values());
    }

    public List<GameObject> getInactiveTrails() {
        return trails.getInactiveTrails();
    }

    public TotemSite getRecommendedSite() {
        return recommendedSite;
    }

    public int getTick() {
        return tick;
    }

    public WoodType getCarriedWood() {
        return carriedWood;
    }

    public int getCarriedLogs() {
        return carriedLogs;
    }

    public int getCarriedDecorations() {
        return carriedDecorations;
    }

    public int getTrailXpActionsLeft() {
        return trailXpActionsLeft;
    }

    public boolean isActive() {
        return inValley();
    }
}
