"""ui.layout: graphs that fill the page."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from proccoli.ui.layout import (GRID_MAX_COLUMNS, GRID_MIN_CHART, LIMITS,  # noqa: E402
                               MIN_GRAPH_HEIGHT, GraphLimits, GridPlan, aspect_height, card_width,
                               max_chart_height,
                               count_rows, fit_heights, group_rows, height_range,
                               is_portrait, needs_update, plan_grid, stack_pair)

WIDE = 2000      # wide enough that the width never caps


class FitHeightsTest(unittest.TestCase):
    def test_rows_share_the_spare_height(self):
        self.assertEqual(fit_heights(700, 100, [WIDE, WIDE]), [300, 300])
        self.assertEqual(fit_heights(700, 100, [WIDE] * 3), [200, 200, 200])

    def test_never_below_the_minimum_so_small_windows_scroll(self):
        self.assertEqual(fit_heights(300, 250, [WIDE, WIDE]), [MIN_GRAPH_HEIGHT] * 2)
        small = GraphLimits(min_height=50)
        self.assertEqual(fit_heights(100, 500, [WIDE], small), [50])

    def test_no_rows(self):
        self.assertEqual(fit_heights(700, 100, []), [])

    def test_grows_and_shrinks_with_the_viewport(self):
        heights = [fit_heights(v, 200, [WIDE, WIDE])[0] for v in (400, 600, 800, 1000)]
        self.assertEqual(heights, sorted(heights))
        self.assertEqual(heights[-1], 400)

    def test_portrait_screen_caps_graphs_by_their_width(self):
        # A 1080x1920 portrait monitor: ~800 px wide column, 1800 px tall.
        heights = fit_heights(1800, 300, [800, 800])
        self.assertEqual(heights, [400, 400])             # 0.5 x width, not 750
        self.assertEqual(fit_heights(5000, 0, [WIDE]), [LIMITS.max_height])

    def test_capped_rows_leave_their_share_to_the_others(self):
        # One full-width row, one row of a narrow pair: the pair caps at 150.
        self.assertEqual(fit_heights(700, 100, [WIDE, 300]), [450, 150])

    def test_cap_never_goes_below_the_minimum(self):
        self.assertEqual(height_range(100), (MIN_GRAPH_HEIGHT, MIN_GRAPH_HEIGHT))
        self.assertEqual(height_range(800), (MIN_GRAPH_HEIGHT, 400))
        self.assertEqual(height_range(4000), (MIN_GRAPH_HEIGHT, LIMITS.max_height))


class PairsTest(unittest.TestCase):
    def test_pairs_stack_when_narrow_or_portrait(self):
        self.assertFalse(stack_pair(1000, 1200, 800))     # landscape, room
        self.assertTrue(stack_pair(500, 1200, 800))        # panes < 280 px
        self.assertTrue(stack_pair(1000, 1000, 1800))      # portrait
        self.assertTrue(is_portrait(1080, 1920))
        self.assertFalse(is_portrait(1920, 1080))
        self.assertFalse(is_portrait(800, 800))


class RowsAndAspectTest(unittest.TestCase):
    def test_group_rows(self):
        self.assertEqual(group_rows([10, 200, 10.5, 400]), [[0, 2], [1], [3]])
        self.assertEqual(group_rows([]), [])

    def test_graphs_side_by_side_share_a_row(self):
        self.assertEqual(count_rows([10, 10, 200, 200.5, 400]), 3)
        self.assertEqual(count_rows([]), 0)
        self.assertEqual(count_rows([300, 10]), 2)

    def test_aspect_height(self):
        self.assertEqual(aspect_height(200, 0.6, 48, 240), 120)
        self.assertEqual(aspect_height(40, 0.6, 48, 240), 48)
        self.assertEqual(aspect_height(1000, 0.6, 48, 240), 240)

    def test_small_changes_are_ignored(self):
        self.assertFalse(needs_update(200, 201))
        self.assertTrue(needs_update(200, 202))




class PlanGridTest(unittest.TestCase):
    """The Overview's N × M grid."""
    CHROME_W, CHROME_H, SPACING = 24, 70, 12

    def plan(self, count, width, height, **kw):
        return plan_grid(count, width, height, self.SPACING, self.CHROME_W, self.CHROME_H, **kw)

    def assertFills(self, plan, height):
        used = plan.height(self.CHROME_H, self.SPACING)
        self.assertLessEqual(used, height)
        self.assertGreater(used, height - plan.rows)      # only rounding is lost

    def test_portrait_monitor_uses_two_tall_columns(self):
        plan = self.plan(8, 1032, 1380)
        self.assertEqual((plan.columns, plan.rows), (2, 4))
        self.assertGreater(plan.chart_height, 240)        # the old cap
        self.assertFills(plan, 1380)

    def test_landscape_uses_more_columns(self):
        plan = self.plan(8, 1600, 530)
        self.assertEqual((plan.columns, plan.rows), (4, 2))
        self.assertFills(plan, 530)

    def test_one_card_on_a_portrait_area_stops_short_of_a_tower(self):
        # it would fill 1310 px, but the chart is 1008 wide.
        plan = self.plan(1, 1032, 1380)
        self.assertEqual((plan.columns, plan.rows), (1, 1))
        self.assertEqual(plan.chart_height, 1008 - 1)
        self.assertEqual(max_chart_height(1008), 1007)

    def test_one_card_fills_a_landscape_area(self):
        plan = self.plan(1, 1600, 700)
        self.assertEqual(plan.chart_height, 700 - self.CHROME_H)

    def test_charts_are_always_shorter_than_wide(self):
        for count in range(1, 13):
            for width, height in ((300, 2000), (400, 900), (1032, 1380), (1032, 3000),
                                  (1600, 530), (2400, 1300)):
                plan = self.plan(count, width, height)
                chart_w = card_width(width, plan.columns, self.SPACING) - self.CHROME_W
                self.assertLess(plan.chart_height, chart_w, (count, width, height, plan))

    def test_filling_beats_a_capped_plan(self):
        # 2 cards, 976 × 674: side by side they'd be capped at their width
        # and leave a gap; stacked, they fill the height.
        plan = self.plan(2, 976, 674)
        self.assertEqual((plan.columns, plan.rows), (1, 2))
        self.assertFills(plan, 674)

    def test_a_wider_ratio_cap(self):
        plan = self.plan(1, 1032, 1380, max_ratio=0.5)
        self.assertLess(plan.chart_height, 0.5 * 1008)

    def test_every_fitting_uncapped_plan_fills_the_height(self):
        for count in range(1, 13):
            for width, height in ((400, 900), (1032, 1380), (1600, 530), (2400, 1300)):
                plan = self.plan(count, width, height)
                self.assertGreaterEqual(plan.columns, 1)
                self.assertGreaterEqual(plan.rows, 1)
                self.assertGreaterEqual(plan.columns * plan.rows, count)
                self.assertLess((plan.rows - 1) * plan.columns, count)   # no empty row
                chart_w = card_width(width, plan.columns, self.SPACING) - self.CHROME_W
                capped = plan.chart_height == max_chart_height(chart_w)
                if plan.chart_height > GRID_MIN_CHART and not capped:
                    self.assertFills(plan, height)

    def test_cards_never_narrower_than_the_minimum(self):
        plan = self.plan(8, 600, 3000)                    # tall: would like many rows anyway
        self.assertLessEqual(plan.columns, 2)
        plan = self.plan(8, 500, 200)                     # too short, but only 1 column fits
        self.assertEqual(plan.columns, 1)
        self.assertEqual(plan.chart_height, GRID_MIN_CHART)

    def test_too_short_prefers_a_plan_that_fits(self):
        # 8 cards in 300 px: only 4 columns × 2 rows keeps charts at the minimum.
        plan = self.plan(8, 1600, 2 * (GRID_MIN_CHART + self.CHROME_H) + self.SPACING)
        self.assertEqual(plan.columns, 4)
        self.assertEqual(plan.chart_height, GRID_MIN_CHART)

    def test_avoids_empty_cells_when_shapes_are_close(self):
        plan = self.plan(4, 1100, 700)
        self.assertEqual(plan.columns * plan.rows, 4)     # 2 × 2, not 3 + 1

    def test_full_rows_beat_a_slightly_better_shape(self):
        # 4 cards, 976 × 436: 3 + 1 would give squarer charts, but 2 × 2 fills the grid.
        plan = plan_grid(4, 976, 436, 12, 24, 81)
        self.assertEqual((plan.columns, plan.rows), (2, 2))

    def test_no_cards(self):
        self.assertEqual(self.plan(0, 800, 600), GridPlan(0, 0, 0))

    def test_columns_capped(self):
        self.assertLessEqual(self.plan(12, 4000, 300).columns, GRID_MAX_COLUMNS)
        self.assertEqual(self.plan(12, 4000, 300, max_columns=6).columns, 6)


class GraphInAreaTest(unittest.TestCase):
    """A graph sharing its area with a legend."""

    def test_area_less_reserve(self):
        from proccoli.ui.layout import graph_in_area
        self.assertEqual(graph_in_area(400, 90), 310)
        self.assertEqual(graph_in_area(400, 0), 400)
        self.assertEqual(graph_in_area(400, -5), 400)

    def test_floor(self):
        from proccoli.ui.layout import MIN_GRAPH_IN_AREA, graph_in_area
        self.assertEqual(graph_in_area(120, 100), MIN_GRAPH_IN_AREA)
        self.assertEqual(graph_in_area(120, 100, floor=10), 20)


class CompactLegendTest(unittest.TestCase):
    """The per-CPU legend drops its values when the chart would be cramped."""

    def test_rule(self):
        from proccoli.ui.layout import COMFORT_GRAPH, use_compact_legend
        self.assertFalse(use_compact_legend(400, 120))
        self.assertTrue(use_compact_legend(220, 140))
        self.assertTrue(use_compact_legend(COMFORT_GRAPH + 99, 100))
        self.assertFalse(use_compact_legend(COMFORT_GRAPH + 100, 100))


if __name__ == "__main__":
    unittest.main()
