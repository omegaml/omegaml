import BaseView from "./baseview.js";
// Model to manage the state of the selected dates
class DateRangeModel extends Backbone.Model {
  defaults() {
    return {
      startDate: null,
      endDate: null,
    };
  }
}
// View to handle rendering and interactions with the date range picker
class DateRangeView extends BaseView {
  constructor(options) {
    _.defaults(options, {
      events: {},
      templateUrl: url_for('static', { filename: "/assets/widgets/sincepick.html"}),
      title: "Select Date Range",
      description: "Please select a start and end date.",
    });
    // DOM events
    _.extend(options.events, {
      "click #toggle-datetime": "toggleRangePicker",
      "click .save-changes": "saveChanges",
      "show.bs.modal": "initializeDates",
    });
    // user events
    _.default(options.events, {
      "since:selected": "eventHandler",
      "range:selected": "eventHandler",
    });
    super(options);
    this.model = new DateRangeModel();
  }
  render() {
    return super
      .render({ title: this.title, description: this.description })
      .then((data) => {
        this.$modal = this.$("#datetimePickerModal"); // Cache the modal element
        this.$modal.modal("hide"); // Initialize Bootstrap modal
        this.initializeDates();
        this.initializeSince();
      })
      .catch((error) => console.error("Error loading template:", error));
  }
  // Initialize the datetime inputs with default values
  initializeDates() {
    const now = new Date();
    const startDate = new Date(now);
    startDate.setMonth(now.getMonth() - 1);
    this.model.set({
      startDate: startDate.toISOString(),
      endDate: now.toISOString(),
    });
    this.$("#start-datetime").val(startDate.toISOString().slice(0, 16));
    this.$("#end-datetime").val(now.toISOString().slice(0, 16));
  }
  initializeSince() {
    const options = [
      { label: "1 Day", days: 1 },
      { label: "3 Days", days: 3 },
      { label: "1 Week", days: 7 },
      { label: "2 Weeks", days: 14 },
      { label: "1 Month", days: 30 },
      { label: "3 Months", days: 90 },
      { label: "6 Months", days: 180 },
      { label: "1 Year", days: 365 },
      { label: "2 Years", days: 730 },
      { label: "5 Years", days: 1825 },
    ];
    const dropdownOptions = this.$("#dropdown-options");
    // Helper function to calculate a date from today
    function calculateDate(daysAgo) {
      const date = new Date();
      date.setDate(date.getDate() - daysAgo);
      return date.toISOString();
    }
    // Generate dropdown items dynamically
    options.forEach((option) => {
      var self = this;
      const button = $("<a>")
        .addClass("dropdown-item")
        .text(option.label)
        .data("days", option.days)
        .on("click", function () {
          const calculatedDate = calculateDate(option.days);
          const endEndDate = new Date().toISOString();
          self.model.set({ startDate: calculatedDate, endDate: endEndDate });
          self.trigger("since:selected", self.model.toJSON());
        });

      const li = $("<li>").append(button);
      dropdownOptions.append(li);
    });
  }
  toggleRangePicker() {
    var self = this;
    // Toggle visibility of the datetime picker
    $("#datetime-picker").toggleClass("d-none"); // Toggle the hidden class
    $("#datetimePickerModal").modal("show");
    // Handle the save changes button click event
    $("#dtrangeSave").on("click", function () {
      const startDate = self.$("#start-datetime").val();
      const endDate = self.$("#end-datetime").val();
      if (startDate && endDate) {
        self.model.set({ startDate: startDate, endDate: endDate });
        self.trigger("range:selected", self.model.toJSON());
        self.$modal.modal("hide"); // Close the modal
      } else {
        alert("Please select both start and end dates.");
      }
    });
  }
}
export default DateRangeView;
