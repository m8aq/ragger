package dev.ragger.valetotems;

import net.runelite.api.gameval.VarbitID;

/**
 * The per-site varbits the game keeps for Vale Totems, indexed by the game's own site number 1-8.
 *
 * <p>gameval declares these as eight separate constants per field, so this table exists to index
 * them by site number. The meaning of each field is taken from its gameval name and has not been
 * confirmed against a live client.
 */
public final class SiteVarbits {

    private static final int[] BASE = {
        VarbitID.ENT_TOTEMS_SITE_1_BASE,
        VarbitID.ENT_TOTEMS_SITE_2_BASE,
        VarbitID.ENT_TOTEMS_SITE_3_BASE,
        VarbitID.ENT_TOTEMS_SITE_4_BASE,
        VarbitID.ENT_TOTEMS_SITE_5_BASE,
        VarbitID.ENT_TOTEMS_SITE_6_BASE,
        VarbitID.ENT_TOTEMS_SITE_7_BASE,
        VarbitID.ENT_TOTEMS_SITE_8_BASE,
    };

    private static final int[] BASE_CARVED = {
        VarbitID.ENT_TOTEMS_SITE_1_BASE_CARVED,
        VarbitID.ENT_TOTEMS_SITE_2_BASE_CARVED,
        VarbitID.ENT_TOTEMS_SITE_3_BASE_CARVED,
        VarbitID.ENT_TOTEMS_SITE_4_BASE_CARVED,
        VarbitID.ENT_TOTEMS_SITE_5_BASE_CARVED,
        VarbitID.ENT_TOTEMS_SITE_6_BASE_CARVED,
        VarbitID.ENT_TOTEMS_SITE_7_BASE_CARVED,
        VarbitID.ENT_TOTEMS_SITE_8_BASE_CARVED,
    };

    private static final int[] LOW = {
        VarbitID.ENT_TOTEMS_SITE_1_LOW,
        VarbitID.ENT_TOTEMS_SITE_2_LOW,
        VarbitID.ENT_TOTEMS_SITE_3_LOW,
        VarbitID.ENT_TOTEMS_SITE_4_LOW,
        VarbitID.ENT_TOTEMS_SITE_5_LOW,
        VarbitID.ENT_TOTEMS_SITE_6_LOW,
        VarbitID.ENT_TOTEMS_SITE_7_LOW,
        VarbitID.ENT_TOTEMS_SITE_8_LOW,
    };

    private static final int[] MID = {
        VarbitID.ENT_TOTEMS_SITE_1_MID,
        VarbitID.ENT_TOTEMS_SITE_2_MID,
        VarbitID.ENT_TOTEMS_SITE_3_MID,
        VarbitID.ENT_TOTEMS_SITE_4_MID,
        VarbitID.ENT_TOTEMS_SITE_5_MID,
        VarbitID.ENT_TOTEMS_SITE_6_MID,
        VarbitID.ENT_TOTEMS_SITE_7_MID,
        VarbitID.ENT_TOTEMS_SITE_8_MID,
    };

    private static final int[] TOP = {
        VarbitID.ENT_TOTEMS_SITE_1_TOP,
        VarbitID.ENT_TOTEMS_SITE_2_TOP,
        VarbitID.ENT_TOTEMS_SITE_3_TOP,
        VarbitID.ENT_TOTEMS_SITE_4_TOP,
        VarbitID.ENT_TOTEMS_SITE_5_TOP,
        VarbitID.ENT_TOTEMS_SITE_6_TOP,
        VarbitID.ENT_TOTEMS_SITE_7_TOP,
        VarbitID.ENT_TOTEMS_SITE_8_TOP,
    };

    private static final int[] DECORATIONS = {
        VarbitID.ENT_TOTEMS_SITE_1_DECORATIONS,
        VarbitID.ENT_TOTEMS_SITE_2_DECORATIONS,
        VarbitID.ENT_TOTEMS_SITE_3_DECORATIONS,
        VarbitID.ENT_TOTEMS_SITE_4_DECORATIONS,
        VarbitID.ENT_TOTEMS_SITE_5_DECORATIONS,
        VarbitID.ENT_TOTEMS_SITE_6_DECORATIONS,
        VarbitID.ENT_TOTEMS_SITE_7_DECORATIONS,
        VarbitID.ENT_TOTEMS_SITE_8_DECORATIONS,
    };

    private static final int[] DECAY = {
        VarbitID.ENT_TOTEMS_SITE_1_DECAY,
        VarbitID.ENT_TOTEMS_SITE_2_DECAY,
        VarbitID.ENT_TOTEMS_SITE_3_DECAY,
        VarbitID.ENT_TOTEMS_SITE_4_DECAY,
        VarbitID.ENT_TOTEMS_SITE_5_DECAY,
        VarbitID.ENT_TOTEMS_SITE_6_DECAY,
        VarbitID.ENT_TOTEMS_SITE_7_DECAY,
        VarbitID.ENT_TOTEMS_SITE_8_DECAY,
    };

    private static final int[] POINTS = {
        VarbitID.ENT_TOTEMS_SITE_1_POINTS,
        VarbitID.ENT_TOTEMS_SITE_2_POINTS,
        VarbitID.ENT_TOTEMS_SITE_3_POINTS,
        VarbitID.ENT_TOTEMS_SITE_4_POINTS,
        VarbitID.ENT_TOTEMS_SITE_5_POINTS,
        VarbitID.ENT_TOTEMS_SITE_6_POINTS,
        VarbitID.ENT_TOTEMS_SITE_7_POINTS,
        VarbitID.ENT_TOTEMS_SITE_8_POINTS,
    };

    private static final int[] TRAIL_BUFF = {
        VarbitID.ENT_TOTEMS_SITE_1_TRAIL_BUFF_ACTIVE,
        VarbitID.ENT_TOTEMS_SITE_2_TRAIL_BUFF_ACTIVE,
        VarbitID.ENT_TOTEMS_SITE_3_TRAIL_BUFF_ACTIVE,
        VarbitID.ENT_TOTEMS_SITE_4_TRAIL_BUFF_ACTIVE,
        VarbitID.ENT_TOTEMS_SITE_5_TRAIL_BUFF_ACTIVE,
        VarbitID.ENT_TOTEMS_SITE_6_TRAIL_BUFF_ACTIVE,
        VarbitID.ENT_TOTEMS_SITE_7_TRAIL_BUFF_ACTIVE,
        VarbitID.ENT_TOTEMS_SITE_8_TRAIL_BUFF_ACTIVE,
    };

    private static final int[] ANIMAL_1 = {
        VarbitID.ENT_TOTEMS_SITE_1_ANIMAL_1,
        VarbitID.ENT_TOTEMS_SITE_2_ANIMAL_1,
        VarbitID.ENT_TOTEMS_SITE_3_ANIMAL_1,
        VarbitID.ENT_TOTEMS_SITE_4_ANIMAL_1,
        VarbitID.ENT_TOTEMS_SITE_5_ANIMAL_1,
        VarbitID.ENT_TOTEMS_SITE_6_ANIMAL_1,
        VarbitID.ENT_TOTEMS_SITE_7_ANIMAL_1,
        VarbitID.ENT_TOTEMS_SITE_8_ANIMAL_1,
    };

    private static final int[] ANIMAL_2 = {
        VarbitID.ENT_TOTEMS_SITE_1_ANIMAL_2,
        VarbitID.ENT_TOTEMS_SITE_2_ANIMAL_2,
        VarbitID.ENT_TOTEMS_SITE_3_ANIMAL_2,
        VarbitID.ENT_TOTEMS_SITE_4_ANIMAL_2,
        VarbitID.ENT_TOTEMS_SITE_5_ANIMAL_2,
        VarbitID.ENT_TOTEMS_SITE_6_ANIMAL_2,
        VarbitID.ENT_TOTEMS_SITE_7_ANIMAL_2,
        VarbitID.ENT_TOTEMS_SITE_8_ANIMAL_2,
    };

    private static final int[] ANIMAL_3 = {
        VarbitID.ENT_TOTEMS_SITE_1_ANIMAL_3,
        VarbitID.ENT_TOTEMS_SITE_2_ANIMAL_3,
        VarbitID.ENT_TOTEMS_SITE_3_ANIMAL_3,
        VarbitID.ENT_TOTEMS_SITE_4_ANIMAL_3,
        VarbitID.ENT_TOTEMS_SITE_5_ANIMAL_3,
        VarbitID.ENT_TOTEMS_SITE_6_ANIMAL_3,
        VarbitID.ENT_TOTEMS_SITE_7_ANIMAL_3,
        VarbitID.ENT_TOTEMS_SITE_8_ANIMAL_3,
    };

    public static final int SITE_COUNT = 8;

    private SiteVarbits() {
    }

    private static int at(final int[] table, final int siteNumber) {
        return table[siteNumber - 1];
    }

    public static int base(final int siteNumber) {
        return at(BASE, siteNumber);
    }

    public static int baseCarved(final int siteNumber) {
        return at(BASE_CARVED, siteNumber);
    }

    public static int low(final int siteNumber) {
        return at(LOW, siteNumber);
    }

    public static int mid(final int siteNumber) {
        return at(MID, siteNumber);
    }

    public static int top(final int siteNumber) {
        return at(TOP, siteNumber);
    }

    public static int decorations(final int siteNumber) {
        return at(DECORATIONS, siteNumber);
    }

    public static int decay(final int siteNumber) {
        return at(DECAY, siteNumber);
    }

    public static int points(final int siteNumber) {
        return at(POINTS, siteNumber);
    }

    public static int trailBuff(final int siteNumber) {
        return at(TRAIL_BUFF, siteNumber);
    }

    public static int animal1(final int siteNumber) {
        return at(ANIMAL_1, siteNumber);
    }

    public static int animal2(final int siteNumber) {
        return at(ANIMAL_2, siteNumber);
    }

    public static int animal3(final int siteNumber) {
        return at(ANIMAL_3, siteNumber);
    }
}
