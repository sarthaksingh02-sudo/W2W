# ECOPE Production: Testing Protocol

This guide outlines the standard procedures for testing Proper Disposal and Improper Disposal (Littering) events in the ECOPE system.

## Prerequisites

1.  **System Running**: Backend, Orchestraor (CV Engine), and Frontend must be running.
2.  **Bin Zone Defined**: The bin zone must be drawn correctly in the CV window.
    *   **Check**: Look for a **Green Polygon** over the bin in the video feed.
    *   **Redefine**: If missing or incorrect, click the window, press `n`, and click 4 points around the bin opening.

## 1. Test: Improper Disposal (Littering)

**Goal**: Verify the system detects an object dropped *outside* the designated bin zone.

**Steps**:
1.  **Pick Up**: Pick up a detectable object (bottle, cup, cell phone).
2.  **Establish Ownership**: Hold the object near your body (chest/stomach/hand) for **2-3 seconds**.
    *   *Log Verification*: Look for `[OWNERSHIP] object X → person Y`.
3.  **Position**: Move to an open area where the floor is visible, clearly **outside** the Green Bin Zone.
4.  **Drop**: Release the object so it falls to the floor.
    *   **Tip**: Do not "throw" it fast. Let it fall naturally or place it down firmly.
    *   **Tip**: Step back slightly (1-2 steps) after dropping to ensure you are not "blocking" the detection of the dropped item and to exceed the "Ownership Distance Threshold".
5.  **Verify**:
    *   **Logs**: `[DROP] object X released` -> `[ZONE] outside bin` -> `[EVENT] violation`.
    *   **Frontend**: Event appears in "Active Violations" list in Red.

## 2. Test: Proper Disposal

**Goal**: Verify the system detects an object dropped *inside* the designated bin zone.

**Steps**:
1.  **Pick Up**: Pick up a detectable object.
2.  **Establish Ownership**: Hold it for **2-3 seconds** to ensure tracking links it to you.
3.  **Approach Bin**: Walk towards the bin.
4.  **Drop in Bin**: Place or drop the object **inside** the Green Polygon area.
    *   **Critical**: The object's track must end (disappear) or stop moving *while* its center is inside the green zone options.
    *   **Tip**: Make sure your hand doesn't block the camera's view of the object entering the zone.
5.  **Verify**:
    *   **Logs**: `[DROP] object X released` -> `[ZONE] inside bin` -> `[EVENT] proper_disposal`.
    *   **Frontend**: Event appears in "Proper Disposals" list in Green.

## Troubleshooting Common Issues

### "Near Miss" / "Owned but close"
*   **Cause**: You are standing too close to the object after dropping it.
*   **Fix**: Step away (1 meter) immediately after the drop. The system needs to see separation between "You" and the "Object".

### "Moving too fast"
*   **Cause**: The object is bouncing or sliding, or the toss was too aggressive.
*   **Fix**: Place the object gently or wait for it to stop wobbling.

### "No Ownership Detected"
*   **Cause**: You picked it up and dropped it too quickly (< 1 second).
*   **Fix**: Hold the object for at least 2 full seconds before dropping.

### Object Not Detected
*   **Cause**: Object is too small, transparent, or occluded.
*   **Fix**: Use standard detectable items like **Bottles, Cups, Cans, or Cell Phones**. Ensure lighting is good.
