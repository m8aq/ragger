package dev.ragger.valetotems;

import net.runelite.api.DynamicObject;
import net.runelite.api.GameObject;
import net.runelite.api.gameval.ObjectID;

import java.util.ArrayList;
import java.util.List;

/**
 * Tracks ent trail flower pairs in the scene.
 *
 * <p>Trails are the game objects {@code ENT_TOTEMS_TRAIL_PART_0} and {@code _1}. Whether a trail
 * has been stepped on shows only in its animation: 12344/12345 while waiting, 12346 once activated.
 * Stepping on both flowers of a pair buffs the ent that left them.
 */
public class EntTrailTracker {

    private static final int INACTIVE_ANIMATION_A = 12344;
    private static final int INACTIVE_ANIMATION_B = 12345;

    private final List<GameObject> trails = new ArrayList<>();

    public boolean isTrail(final GameObject object) {
        return object.getId() == ObjectID.ENT_TOTEMS_TRAIL_PART_0
            || object.getId() == ObjectID.ENT_TOTEMS_TRAIL_PART_1;
    }

    public void add(final GameObject object) {
        if (isTrail(object)) {
            trails.add(object);
        }
    }

    public void remove(final GameObject object) {
        trails.remove(object);
    }

    public void clear() {
        trails.clear();
    }

    /** Trails not yet stepped on — the ones worth running over. */
    public List<GameObject> getInactiveTrails() {
        final List<GameObject> inactive = new ArrayList<>();

        for (final GameObject trail : trails) {
            if (isInactive(trail)) {
                inactive.add(trail);
            }
        }

        return inactive;
    }

    private boolean isInactive(final GameObject trail) {
        if (!(trail.getRenderable() instanceof DynamicObject dynamic)) {
            return false;
        }

        if (dynamic.getAnimation() == null) {
            return false;
        }

        final int animation = dynamic.getAnimation().getId();
        return animation == INACTIVE_ANIMATION_A || animation == INACTIVE_ANIMATION_B;
    }
}
