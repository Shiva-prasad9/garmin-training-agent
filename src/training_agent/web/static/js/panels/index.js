// The dashboard is this list. To add a panel: create a file that exports
// { id, title, render(section, data, state) } and add one line here.
import nextstep from "./nextstep.js";
import insights from "./insights.js";
import status from "./status.js";
import week from "./week.js";
import quest from "./quest.js";
import readiness from "./readiness.js";
import trends from "./trends.js";
import activities from "./activities.js";

import guide from "./guide.js";
export { guide };
export const panels = [status, quest, readiness, week, trends, activities];

// The Insights page (left menu) shows these instead of the overview panels.
export const insightPanels = [nextstep, insights];
