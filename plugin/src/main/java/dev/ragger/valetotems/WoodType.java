package dev.ragger.valetotems;

/**
 * Wood tiers usable in Vale Totems.
 *
 * <p>{@code visits} is the totem's starting durability: the number of ent visits it survives before
 * collapsing. {@code offeringsByDecorations} is indexed 0..4 and gives the offerings a single ent
 * visit leaves for that many decorations applied.
 */
public enum WoodType {

    OAK("Oak", 20, 2, new int[]{2, 4, 6, 8, 10}),
    WILLOW("Willow", 35, 3, new int[]{2, 4, 6, 8, 10}),
    MAPLE("Maple", 50, 4, new int[]{2, 4, 6, 8, 10}),
    YEW("Yew", 65, 5, new int[]{3, 5, 8, 10, 13}),
    MAGIC("Magic", 80, 6, new int[]{3, 6, 9, 12, 15}),
    REDWOOD("Redwood", 90, 7, new int[]{3, 6, 9, 12, 15});

    private final String displayName;
    private final int fletchingLevel;
    private final int visits;
    private final int[] offeringsByDecorations;

    WoodType(final String displayName, final int fletchingLevel, final int visits, final int[] offeringsByDecorations) {
        this.displayName = displayName;
        this.fletchingLevel = fletchingLevel;
        this.visits = visits;
        this.offeringsByDecorations = offeringsByDecorations;
    }

    public String getDisplayName() {
        return displayName;
    }

    public int getFletchingLevel() {
        return fletchingLevel;
    }

    public int getVisits() {
        return visits;
    }

    public int offeringsFor(final int decorations) {
        final int clamped = Math.max(0, Math.min(4, decorations));
        return offeringsByDecorations[clamped];
    }

    public int maxOfferings() {
        return offeringsFor(4) * visits;
    }

    /**
     * Resolves the wood tier from an object or item name such as "Yew totem" or "Yew longbow (u)".
     * Returns null when no tier name appears in the string.
     */
    public static WoodType fromName(final String name) {
        if (name == null) {
            return null;
        }

        final String lower = name.toLowerCase();

        for (final WoodType wood : values()) {
            if (lower.contains(wood.displayName.toLowerCase())) {
                return wood;
            }
        }

        return null;
    }
}
