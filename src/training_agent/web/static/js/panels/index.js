// The dashboard is this list. To add a panel: create a file that exports
// { id, title, render(section, data, state) } and add one line here.
import status from "./status.js";
import week from "./week.js";
import quest from "./quest.js";
import trends from "./trends.js";
import activities from "./activities.js";
import gymlog from "./gymlog.js";

export const panels = [status, week, quest, trends, activities, gymlog];
