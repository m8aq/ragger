package dev.ragger.valetotems;

import net.runelite.api.NPC;
import net.runelite.api.gameval.NpcID;

/**
 * A single ent walking the valley loop.
 *
 * <p>The ent's NPC ID carries its state: {@code ENT_TOTEMS_ENT} is a plain ent,
 * {@code ENT_TOTEMS_ENT_BUFFED} is one carrying an activated ent trail bonus, and
 * {@code ENT_TOTEMS_ENT_DESTINATION_1} through {@code _8} name the site it is walking to. Ents that
 * report a plain ID give no destination, so the countdown falls back to the 80-tick cadence the wiki
 * documents, anchored on the last arrival actually observed.
 */
public class TrackedEnt {

    public static final int MOVE_PERIOD_TICKS = 80;
    public static final int ADMIRE_TICKS = 14;
    public static final int LINGER_TICKS = 8;

    private static final int[] DESTINATION_IDS = {
        NpcID.ENT_TOTEMS_ENT_DESTINATION_1,
        NpcID.ENT_TOTEMS_ENT_DESTINATION_2,
        NpcID.ENT_TOTEMS_ENT_DESTINATION_3,
        NpcID.ENT_TOTEMS_ENT_DESTINATION_4,
        NpcID.ENT_TOTEMS_ENT_DESTINATION_5,
        NpcID.ENT_TOTEMS_ENT_DESTINATION_6,
        NpcID.ENT_TOTEMS_ENT_DESTINATION_7,
        NpcID.ENT_TOTEMS_ENT_DESTINATION_8,
    };

    private final NPC npc;

    private int currentSiteNumber;
    private int lastArrivalTick = Integer.MIN_VALUE;
    private boolean atSite;

    public TrackedEnt(final NPC npc) {
        this.npc = npc;
    }

    public static boolean isEnt(final int npcId) {
        if (npcId == NpcID.ENT_TOTEMS_ENT || npcId == NpcID.ENT_TOTEMS_ENT_BUFFED) {
            return true;
        }

        return destinationOf(npcId) > 0;
    }

    /**
     * The site number encoded in an ent's NPC ID, or 0 when the ID carries no destination.
     */
    public static int destinationOf(final int npcId) {
        for (int i = 0; i < DESTINATION_IDS.length; i++) {
            if (DESTINATION_IDS[i] == npcId) {
                return i + 1;
            }
        }

        return 0;
    }

    public NPC getNpc() {
        return npc;
    }

    public boolean isBuffed() {
        return npc.getId() == NpcID.ENT_TOTEMS_ENT_BUFFED;
    }

    public int getCurrentSiteNumber() {
        return currentSiteNumber;
    }

    public boolean isAtSite() {
        return atSite;
    }

    public void arriveAt(final int siteNumber, final int tick) {
        if (atSite && currentSiteNumber == siteNumber) {
            return;
        }

        atSite = true;
        currentSiteNumber = siteNumber;
        lastArrivalTick = tick;
    }

    public void leaveSite() {
        atSite = false;
    }

    public boolean hasArrivalAnchor() {
        return lastArrivalTick != Integer.MIN_VALUE;
    }

    /**
     * The site this ent is walking to. Read from the NPC ID when it encodes one, otherwise the next
     * site clockwise by number, since ents walk the eight sites in order.
     */
    public int nextSiteNumber() {
        final int encoded = destinationOf(npc.getId());

        if (encoded > 0) {
            return encoded;
        }

        if (currentSiteNumber < 1) {
            return 0;
        }

        return currentSiteNumber % SiteVarbits.SITE_COUNT + 1;
    }

    /**
     * Ticks until this ent is predicted to reach its next site, or -1 with no arrival anchor yet.
     */
    public int ticksToNextSite(final int tick) {
        if (!hasArrivalAnchor()) {
            return -1;
        }

        return Math.max(0, MOVE_PERIOD_TICKS - (tick - lastArrivalTick));
    }

    /**
     * Ticks left in the window where decorations added to the current totem still count.
     * Negative once the window has closed.
     */
    public int ticksLeftInAdmireWindow(final int tick) {
        if (!atSite || !hasArrivalAnchor()) {
            return -1;
        }

        return ADMIRE_TICKS - (tick - lastArrivalTick);
    }
}
