package dev.ragger.valetotems;

import net.runelite.api.coords.WorldPoint;

import java.util.ArrayList;
import java.util.List;

/**
 * One of the eight totem sites, keyed by the game's own site number 1-8.
 *
 * <p>All state comes from varbits, so it is known even when the site is far outside the loaded
 * scene. The map position comes from the site's permanent base multiloc object
 * ({@code ObjectID1.ENT_TOTEMS_SITE_n_BASE}), which is bound the first time that object is seen in
 * the scene; until then the site is listed in the panel but not drawn on the map.
 *
 * <p>Encodings (confirmed against the cache's varbit bit layout and the plugin-hub
 * totem-fletching plugin): {@code BASE} is 0 when nothing stands here and 1-6 for the wood tier
 * oak..redwood; {@code BASE_CARVED} is a boolean; {@code LOW}/{@code MID}/{@code TOP} are complete
 * when greater than 4, and a completed segment's value is the carved spirit's ID plus 9;
 * {@code DECORATIONS} counts 0-4; {@code DECAY} is the durability leaves remaining;
 * {@code POINTS} is the uncollected offerings pile, soft-capped at 15,000.
 */
public class TotemSite {

    public static final int PLANE = 0;
    public static final int MAX_OFFERINGS = 15_000;

    /** A segment varbit above this value means the segment is fully carved. */
    private static final int SEGMENT_COMPLETE_THRESHOLD = 4;

    private final int number;

    private WorldPoint point;
    private int base;
    private boolean baseCarved;
    private int low;
    private int mid;
    private int top;
    private int decorations;
    private int decay;
    private int offerings;
    private boolean trailBuffActive;
    private int spirit1;
    private int spirit2;
    private int spirit3;

    private TotemSite(final int number) {
        this.number = number;
    }

    public static List<TotemSite> buildAll() {
        final List<TotemSite> sites = new ArrayList<>(SiteVarbits.SITE_COUNT);

        for (int number = 1; number <= SiteVarbits.SITE_COUNT; number++) {
            sites.add(new TotemSite(number));
        }

        return sites;
    }

    public int getNumber() {
        return number;
    }

    public WorldPoint getPoint() {
        return point;
    }

    public void setPoint(final WorldPoint point) {
        this.point = point;
    }

    public boolean hasPoint() {
        return point != null;
    }

    public void setBase(final int base) {
        this.base = base;
    }

    public void setBaseCarved(final boolean baseCarved) {
        this.baseCarved = baseCarved;
    }

    public void setSegments(final int low, final int mid, final int top) {
        this.low = low;
        this.mid = mid;
        this.top = top;
    }

    public int getDecorations() {
        return decorations;
    }

    public void setDecorations(final int decorations) {
        this.decorations = decorations;
    }

    public int getDecay() {
        return decay;
    }

    public void setDecay(final int decay) {
        this.decay = decay;
    }

    public int getOfferings() {
        return offerings;
    }

    public void setOfferings(final int offerings) {
        this.offerings = offerings;
    }

    public boolean isOfferingsCapped() {
        return offerings >= MAX_OFFERINGS;
    }

    public boolean isTrailBuffActive() {
        return trailBuffActive;
    }

    public void setTrailBuffActive(final boolean trailBuffActive) {
        this.trailBuffActive = trailBuffActive;
    }

    public void setSpirits(final int spirit1, final int spirit2, final int spirit3) {
        this.spirit1 = spirit1;
        this.spirit2 = spirit2;
        this.spirit3 = spirit3;
    }

    public int[] getSpirits() {
        return new int[]{spirit1, spirit2, spirit3};
    }

    /** The wood tier standing here, read from the BASE varbit. Null when the site is bare. */
    public WoodType getWood() {
        if (base < 1 || base > WoodType.values().length) {
            return null;
        }

        return WoodType.values()[base - 1];
    }

    public boolean hasTotem() {
        return base != 0;
    }

    public int getCarvedSegments() {
        int carved = baseCarved ? 1 : 0;

        if (low > SEGMENT_COMPLETE_THRESHOLD) {
            carved++;
        }

        if (mid > SEGMENT_COMPLETE_THRESHOLD) {
            carved++;
        }

        if (top > SEGMENT_COMPLETE_THRESHOLD) {
            carved++;
        }

        return carved;
    }

    public SiteStage getStage() {
        if (!hasTotem()) {
            return SiteStage.EMPTY;
        }

        if (getCarvedSegments() < 4) {
            return SiteStage.CARVING;
        }

        return decorations > 0 ? SiteStage.DECORATED : SiteStage.CARVED;
    }

    public boolean isComplete() {
        return hasTotem() && getCarvedSegments() >= 4 && decorations >= 4;
    }

    public boolean needsWork() {
        return !isComplete();
    }

    /** Offerings a single ent visit would leave right now. Zero when the site is bare. */
    public int offeringsPerVisit() {
        final WoodType wood = getWood();

        if (wood == null) {
            return 0;
        }

        return wood.offeringsFor(decorations);
    }
}
