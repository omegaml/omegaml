/**
 * Class representing a tab order manager for a tabbed interface.
 *
 * The TabOrder class allows for dynamic reordering of bootstrap 4 tabs
 * based on a provided mapping of id => ordinal. It can assign default order
 * values to tabs that are not specified in the order map and reorder
 * the tabs in the DOM accordingly. The default order starts at 10 and increments
 * by 10 for each unmentioned tab.
 *
 * @class TabOrder
 *
 * @example
 * const orderMap = {
 *   'tab1': 20,
 *   'tab2': 30,
 *   'tab3': 40
 * };
 * const tabOrder = new TabOrder('.nav-tabs', orderMap);
 * tabOrder.apply();
 */
class TabOrder {
  constructor(tabSelector, orderMap) {
    this.$tabList = $(tabSelector);
    this.setTabOrder(orderMap);
  }
  // Method to set data-order attribute on all tabs based on the provided order map
  setTabOrder(orderMap) {
    var defaultOrderStart = 10; // Start from the next available index
    this.$tabList.children(".nav-item").each((index, element) => {
      const $element = $(element);
      const tabName = $element.find("a").attr("id").toLowerCase(); // Get the tab name
      // Check if the tab name exists in the orderMap
      if (orderMap.hasOwnProperty(tabName) && !$element.data("order")) {
        $element.attr("data-order", orderMap[tabName]);
      } else if (!$element.data("order")) {
        // Assign a default order for unmentioned tabs
        $element.attr("data-order", defaultOrderStart);
        defaultOrderStart += 10; // Increment for the next unmentioned tab
      }
    });
  }
  // Method to reorder tabs based on data-order attribute
  apply() {
    const $tabs = this.$tabList.children(".nav-item");
    // Sort tabs based on the data-order attribute
    const sortedTabs = $tabs.sort((a, b) => {
      return parseInt($(a).data("order")) - parseInt($(b).data("order"));
    });
    // Clear the current tab list
    this.$tabList.empty();
    // Append sorted tabs back to the tab list
    this.$tabList.append(sortedTabs);
    this.$tabList.children(".nav-item").children("a").removeClass("active"); // Remove active class from all tabs
    this.$tabList.children(".nav-item").children("a").first().tab("show"); // Show the first tab
  }
}
