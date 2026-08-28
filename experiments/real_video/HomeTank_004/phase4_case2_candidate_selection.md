# HomeTank_004 Phase 4 Case 2 Candidate Selection

Status: `CASE2_MANUAL_REFERENCE_REQUIRED`

## Purpose and boundary

Case 1 remains unchanged: ruler delta `+0.1 mm`, absolute discrepancy `5.867183 mm`, classification `PHYSICAL_VALIDATION_COMPLETED_BUT_REFERENCE_CHANGE_TOO_SMALL_FOR_STRONG_ACCURACY_CLAIM`.

Case 2 sought a visually clearer physical state. Candidate preparation used only canonical cam1 video appearance and R0 synchronization availability. It did **not** read WASS output, XYZ, reconstructed height, ruler OCR, or ruler values. The user subsequently selected `candidate_02` solely from the visual previews; only that candidate received one formal WASS run.

## Image-only extraction method

The cam1 Wave video was decoded at 5 Hz to 320×180 grayscale for scoring. A fixed full-scene water/ruler region `(45,35,240,120)` at that resolution was compared with the 20 s reference using mean absolute frame difference after subtracting each frame's ROI median. This reduces global brightness-offset influence. High-change samples were separated by 1.0 s temporal non-maximum suppression; the 1.0 s value is only candidate deduplication, not a wave-period model. Top candidates were visually screened only to retain the uncropped ruler/water region and distinct episodes.

The committed previews are exact-PTS cam1 frames, canonical rotation 0°, uniformly scaled from 1920×1080 to 960×540 without cropping. They are selection previews, not formal coordinate-picking images.

## Candidates

| ID | Requested left time | Actual cam1 PTS / time | Left R0 time | Pair residual | Sync status |
|---|---:|---|---:|---:|---|
| candidate_01 | 25.265406 s | pts_2268060 / 25.200667 s | 25.266733 s | -0.6605 ms | accepted |
| candidate_02 | 29.465406 s | pts_2646070 / 29.400778 s | 29.465178 s | +1.0055 ms | accepted |
| candidate_03 | 89.265406 s | pts_8028214 / 89.202378 s | 89.261011 s | +6.7725 ms | accepted |
| candidate_04 | 94.665405 s | pts_8512727 / 94.585856 s | 94.659244 s | -7.9825 ms | accepted |
| candidate_05 | 116.265406 s | pts_10458279 / 116.203100 s | 116.268467 s | +0.0385 ms | accepted |
| candidate_06 | 136.865406 s | pts_12312329 / 136.803656 s | 136.861200 s | +7.8615 ms | accepted |

All `accepted` entries mean R0 is available under the existing on-demand engineering tolerance. Strict frame-level synchronization remains unestablished and is not rewritten.

## User selection result

The user selected `candidate_02` after reviewing [the contact sheet](phase4_case2_candidate_frames/phase4_case2_candidates_contact_sheet.png), using only these observations:

1. The water surface is visibly different from the Static 9.1 mm state.
2. The waterline beside the ruler is clear enough for a manual reading.
3. Reflection, hand, or container motion does not fully obscure that location.
4. Prefer an apparently larger physical water-level difference, but do not inspect any reconstruction result.

Only the selected R0 pair ran through the existing single-frame backend and received a separately named [Case 2 frozen baseline](phase4_validation_case2.md). Case 1 was not replaced; the remaining five candidates were not reconstructed.

## Stop point

The formal candidate_02 reconstruction and QA are frozen. Work now stops pending the user's independent ruler reading and waterline click on the formal full-resolution reference image.
