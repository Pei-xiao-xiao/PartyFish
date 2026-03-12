import unittest

from src.services.fishing_service import FishingService


class FakeVision:
    def __init__(self, matches=None):
        self.matches = matches or {}

    def find_template(self, key, region=None, threshold=0.0):
        return bool(self.matches.get(key, False))


class FishingServiceSmartTests(unittest.TestCase):
    def test_compute_smart_release_angle_clamps_to_fixed_danger_angle(self):
        self.assertEqual(FishingService._compute_smart_release_angle(-10.0), 34.0)
        self.assertEqual(FishingService._compute_smart_release_angle(0.0), 34.0)
        self.assertEqual(FishingService._compute_smart_release_angle(18.0), 52.0)

    def test_compute_smart_release_angle_clamps_high_values(self):
        self.assertEqual(FishingService._compute_smart_release_angle(500.0), 170.0)

    def test_resolve_smart_pointer_state_prefers_fused_result(self):
        legacy_state = {
            "angle": 141.8,
            "score": 0.93,
            "pointer": (380.0, 674.0),
            "method": "template",
        }
        debug_result = {
            "best_candidate": {
                "angle": 26.8,
                "score": 0.28,
                "tip_point": (240.0, 20.0),
                "root_point": (220.0, 40.0),
                "rotation": 12,
            },
            "candidates": [
                {
                    "angle": 26.8,
                    "score": 0.28,
                    "tip_point": (240.0, 20.0),
                    "root_point": (220.0, 40.0),
                    "rotation": 12,
                }
            ],
        }
        motion_result = {
            "best_candidate": {
                "angle": 33.6,
                "score": 180.0,
                "tip_point": (238.0, 24.0),
                "root_point": (220.0, 42.0),
            }
        }

        pointer_state = FishingService._resolve_smart_pointer_state(
            gauge_region=(100, 200, 276, 104),
            legacy_state=legacy_state,
            debug_result=debug_result,
            motion_result=motion_result,
        )

        self.assertIsNotNone(pointer_state)
        self.assertEqual(pointer_state["source"], "fused")
        self.assertAlmostEqual(pointer_state["angle"], 30.8, delta=3.5)

    def test_should_release_smart_pointer_at_configured_threshold(self):
        decision = FishingService._should_release_smart_pointer(
            current_angle=52.0,
            configured_release_angle=52.0,
            danger_release_angle=34.0,
        )
        self.assertEqual(decision, "threshold")

    def test_should_release_smart_pointer_with_small_tolerance(self):
        decision = FishingService._should_release_smart_pointer(
            current_angle=52.8,
            configured_release_angle=52.0,
            danger_release_angle=34.0,
            release_tolerance=1.0,
        )
        self.assertEqual(decision, "threshold")

    def test_should_release_smart_pointer_immediately_in_danger_zone(self):
        decision = FishingService._should_release_smart_pointer(
            current_angle=33.9,
            configured_release_angle=52.0,
            danger_release_angle=34.0,
        )
        self.assertEqual(decision, "danger")

    def test_should_release_smart_pointer_when_fast_drop_nears_danger(self):
        decision = FishingService._should_release_smart_pointer(
            current_angle=39.5,
            configured_release_angle=34.0,
            danger_release_angle=34.0,
            previous_angle=48.0,
            danger_guard_angle=6.0,
            fast_drop_threshold=4.0,
        )
        self.assertEqual(decision, "danger_guard")

    def test_should_release_smart_pointer_when_fast_drop_nears_threshold(self):
        decision = FishingService._should_release_smart_pointer(
            current_angle=74.0,
            configured_release_angle=68.0,
            danger_release_angle=34.0,
            previous_angle=86.0,
            threshold_guard_angle=8.0,
            threshold_fast_drop_threshold=6.0,
        )
        self.assertEqual(decision, "threshold_fast_guard")

    def test_should_release_smart_pointer_when_tracking_breaks_near_threshold(self):
        decision = FishingService._should_release_smart_pointer(
            current_angle=54.3,
            configured_release_angle=52.0,
            danger_release_angle=34.0,
            suppressed_reverse_jump=True,
            release_tolerance=1.0,
            near_threshold_release_margin=3.0,
        )
        self.assertEqual(decision, "threshold_guard")

    def test_should_release_on_pointer_loss_near_threshold(self):
        decision = FishingService._should_release_on_pointer_loss(
            last_angle=54.2,
            configured_release_angle=52.0,
            pointer_missing_count=2,
            missing_release_count=2,
            missing_release_margin=3.0,
        )
        self.assertEqual(decision, "threshold_loss_guard")

    def test_should_not_release_on_pointer_loss_when_too_far_from_threshold(self):
        decision = FishingService._should_release_on_pointer_loss(
            last_angle=60.0,
            configured_release_angle=52.0,
            pointer_missing_count=2,
            missing_release_count=2,
            missing_release_margin=3.0,
        )
        self.assertIsNone(decision)

    def test_compute_smart_release_duration_keeps_normal_release_time(self):
        duration = FishingService._compute_smart_release_duration(
            smart_release_time=0.6,
            release_reason="threshold",
        )
        self.assertAlmostEqual(duration, 0.6, delta=1e-6)

    def test_compute_smart_release_duration_caps_threshold_guard(self):
        duration = FishingService._compute_smart_release_duration(
            smart_release_time=0.6,
            release_reason="threshold_guard",
        )
        self.assertAlmostEqual(duration, 0.12, delta=1e-6)

    def test_compute_smart_release_duration_caps_threshold_loss_guard(self):
        duration = FishingService._compute_smart_release_duration(
            smart_release_time=0.6,
            release_reason="threshold_loss_guard",
        )
        self.assertAlmostEqual(duration, 0.12, delta=1e-6)

    def test_initial_threshold_release_is_not_armed_by_low_startup_angle(self):
        armed = FishingService._should_arm_initial_threshold_release(
            current_angle=51.0,
            configured_release_angle=68.0,
            hold_started_at=100.0,
            now=100.1,
        )
        self.assertFalse(armed)

    def test_initial_threshold_release_arms_after_safe_angle(self):
        armed = FishingService._should_arm_initial_threshold_release(
            current_angle=72.0,
            configured_release_angle=68.0,
            hold_started_at=100.0,
            now=100.1,
        )
        self.assertTrue(armed)

    def test_initial_threshold_release_arms_after_startup_timeout(self):
        armed = FishingService._should_arm_initial_threshold_release(
            current_angle=51.0,
            configured_release_angle=68.0,
            hold_started_at=100.0,
            now=100.5,
        )
        self.assertTrue(armed)

    def test_initial_release_guard_blocks_danger_before_arm(self):
        armed = FishingService._should_arm_initial_threshold_release(
            current_angle=33.0,
            configured_release_angle=68.0,
            hold_started_at=100.0,
            now=100.1,
        )
        self.assertFalse(armed)

    def test_initial_threshold_log_is_suppressed_near_hook_time(self):
        should_log = FishingService._should_log_initial_threshold_release(
            reel_started_at=100.0,
            now=100.6,
        )
        self.assertFalse(should_log)

    def test_initial_threshold_log_is_allowed_after_suppress_window(self):
        should_log = FishingService._should_log_initial_threshold_release(
            reel_started_at=100.0,
            now=101.3,
        )
        self.assertTrue(should_log)

    def test_build_smart_pointer_runtime_log_contains_thresholds(self):
        log_line = FishingService._build_smart_pointer_runtime_log(
            pointer_state={"angle": 51.6, "source": "fused", "score": 3.2},
            configured_release_angle=52.0,
            danger_release_angle=34.0,
            release_reason="threshold",
        )

        self.assertIn("angle=51.6", log_line)
        self.assertIn("threshold=52.0", log_line)
        self.assertIn("danger=34.0", log_line)
        self.assertIn("source=fused", log_line)
        self.assertIn("release=threshold", log_line)

    def test_has_reel_in_success_signal_detects_star(self):
        vision = FakeVision(matches={"star_grayscale": True})

        result = FishingService._has_reel_in_success_signal(
            vision=vision,
            star_region=(0, 0, 10, 10),
            shangyu_region=(0, 0, 10, 10),
        )

        self.assertTrue(result)

    def test_has_reel_in_success_signal_detects_catch_popup(self):
        vision = FakeVision(matches={"shangyu_grayscale": True})

        result = FishingService._has_reel_in_success_signal(
            vision=vision,
            star_region=(0, 0, 10, 10),
            shangyu_region=(0, 0, 10, 10),
        )

        self.assertTrue(result)

    def test_apply_hold_direction_filter_accepts_first_angle(self):
        angle, filter_reason = FishingService._apply_hold_direction_filter(
            current_angle=96.0,
            previous_angle=None,
        )
        self.assertEqual(angle, 96.0)
        self.assertIsNone(filter_reason)

    def test_apply_hold_direction_filter_accepts_decreasing_angle(self):
        angle, filter_reason = FishingService._apply_hold_direction_filter(
            current_angle=72.0,
            previous_angle=80.0,
        )
        self.assertEqual(angle, 72.0)
        self.assertIsNone(filter_reason)

    def test_apply_hold_direction_filter_blocks_large_reverse_jump(self):
        angle, filter_reason = FishingService._apply_hold_direction_filter(
            current_angle=124.0,
            previous_angle=68.0,
        )
        self.assertEqual(angle, 68.0)
        self.assertEqual(filter_reason, "reverse_jump")

    def test_apply_hold_direction_filter_blocks_large_forward_drop(self):
        angle, filter_reason = FishingService._apply_hold_direction_filter(
            current_angle=31.7,
            previous_angle=152.8,
        )
        self.assertEqual(angle, 152.8)
        self.assertEqual(filter_reason, "forward_jump")


if __name__ == "__main__":
    unittest.main()
