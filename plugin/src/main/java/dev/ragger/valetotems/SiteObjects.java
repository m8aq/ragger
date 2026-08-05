package dev.ragger.valetotems;

import net.runelite.api.gameval.ObjectID;

/**
 * The permanent per-site multiloc objects. {@code ENT_TOTEMS_SITE_n_BASE} stands at every site in
 * all states (its rendered impostor changes with the site's varbits), so its spawn pins down where
 * site n is. {@code ENT_TOTEMS_SITE_n_OFFERINGS} is the offerings pile next to it.
 */
public final class SiteObjects {

    private static final int[] BASE = {
        ObjectID.ENT_TOTEMS_SITE_1_BASE,
        ObjectID.ENT_TOTEMS_SITE_2_BASE,
        ObjectID.ENT_TOTEMS_SITE_3_BASE,
        ObjectID.ENT_TOTEMS_SITE_4_BASE,
        ObjectID.ENT_TOTEMS_SITE_5_BASE,
        ObjectID.ENT_TOTEMS_SITE_6_BASE,
        ObjectID.ENT_TOTEMS_SITE_7_BASE,
        ObjectID.ENT_TOTEMS_SITE_8_BASE,
    };

    private SiteObjects() {
    }

    /** The site number 1-8 whose base multiloc has this object ID, or 0 for any other object. */
    public static int siteOfBaseObject(final int objectId) {
        for (int i = 0; i < BASE.length; i++) {
            if (BASE[i] == objectId) {
                return i + 1;
            }
        }

        return 0;
    }
}
