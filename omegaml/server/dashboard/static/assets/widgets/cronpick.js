// https://chatgpt.com/share/671838d3-0d34-800f-aafb-b3c743b6cf8b
import BaseView from "./baseview.js";

export default class CronView extends BaseView {
  constructor(options) {
    _.defaults(options, {
      events: {},
      templateUrl: url_for("static", {
        filename: "/assets/widgets/cronpick.html",
      }),
      title: "Select Date Range",
      description: "Please select a start and end date.",
    });
    // DOM events
    _.extend(options.events, {
      "click #applyBtn": "applyCronExpression",
      "change #cronExpression": "manualInput",
      "show.bs.modal #cronModal": "openModal",
      "click #confirmDeleteButton": "deleteCron",
    });
    // user events
    _.defaults(options.events, {
      "cron:selected": "eventHandler",
    });
    super(options);
    this.cronExpression = options.cronExpression || "* * * * *";
    this.render();
  }

  render() {
    super
      .render({ title: this.title, description: this.description })
      .then((data) => {
        this.populateTimeSelectors();
        this.parseCronExpression(
          $("#cronExpression").val(this.cronExpression).val()
        );
        this.delegateEvents();
      });
  }

  // Populate hour, minute, and day selectors
  populateTimeSelectors() {
    const hourSelectors =
      "#dailyHourSelect, #weeklyHourSelect, #monthlyHourSelect";
    for (let i = 0; i < 24; i++) {
      const hour = i.toString().padStart(2, "0");
      $(hourSelectors).append(`<option value="${i}">${hour}:00</option>`);
    }

    const minuteSelectors =
      "#dailyMinuteSelect, #weeklyMinuteSelect, #monthlyMinuteSelect";
    for (let i = 0; i < 60; i++) {
      const minute = i.toString().padStart(2, "0");
      $(minuteSelectors).append(`<option value="${i}">${minute}</option>`);
    }

    for (let i = 1; i <= 31; i++) {
      $("#monthlyDaySelect").append(`<option value="${i}">${i}</option>`);
    }
  }

  // Parse cron expression and select appropriate tab
  parseCronExpression(cronExp) {
    try {
      const parts = cronExp.trim().split(" ");
      if (parts.length !== 5) throw new Error("Invalid cron expression format");
      const [minute, hour, dayMonth, month, dayWeek] = parts;
      this.resetForm();

      if (minute.startsWith("*/")) {
        $("#minuteSelect").val(minute.substring(2));
        $('#cronTabs a[href="#minutes"]').tab("show");
      } else if (minute === "0" && hour.startsWith("*/")) {
        $("#hourSelect").val(hour.substring(2));
        $('#cronTabs a[href="#hourly"]').tab("show");
      } else if (dayWeek !== "*") {
        $('#cronTabs a[href="#weekly"]').tab("show");
        const days = dayWeek.split(",");
        days.forEach((day) => {
          $(`#weekly input[value="${day}"]`)
            .prop("checked", true)
            .closest(".btn")
            .addClass("active");
        });
        $("#weeklyHourSelect").val(parseInt(hour));
        $("#weeklyMinuteSelect").val(parseInt(minute));
      } else if (dayMonth !== "*") {
        $('#cronTabs a[href="#monthly"]').tab("show");
        $("#monthlyDaySelect").val(parseInt(dayMonth));
        $("#monthlyHourSelect").val(parseInt(hour));
        $("#monthlyMinuteSelect").val(parseInt(minute));
      } else {
        $('#cronTabs a[href="#daily"]').tab("show");
        $("#dailyHourSelect").val(parseInt(hour));
        $("#dailyMinuteSelect").val(parseInt(minute));
      }

      $("#cronError").text("");
    } catch (error) {
      $("#cronError").text("Invalid cron expression");
    }
  }

  // Generate the cron expression based on the selected tab
  generateCronExpression() {
    const activeTab = $("#cronTabs .nav-link.active").attr("href");
    let cronExp = "";

    switch (activeTab) {
      case "#minutes":
        const minutes = $("#minuteSelect").val();
        cronExp = `*/${minutes} * * * *`;
        break;
      case "#hourly":
        const hours = $("#hourSelect").val();
        cronExp = `0 */${hours} * * *`;
        break;
      case "#daily":
        const dailyHour = $("#dailyHourSelect").val();
        const dailyMinute = $("#dailyMinuteSelect").val();
        cronExp = `${dailyMinute} ${dailyHour} * * *`;
        break;
      case "#weekly":
        const weekdays = [];
        $('#weekly input[type="checkbox"]:checked').each(function () {
          weekdays.push($(this).val());
        });
        const weeklyHour = $("#weeklyHourSelect").val();
        const weeklyMinute = $("#weeklyMinuteSelect").val();
        cronExp = `${weeklyMinute} ${weeklyHour} * * ${weekdays.join(",")}`;
        break;
      case "#monthly":
        const monthlyDay = $("#monthlyDaySelect").val();
        const monthlyHour = $("#monthlyHourSelect").val();
        const monthlyMinute = $("#monthlyMinuteSelect").val();
        cronExp = `${monthlyMinute} ${monthlyHour} ${monthlyDay} * *`;
        break;
    }

    return cronExp;
  }

  // Event handler when 'Apply' button is clicked
  applyCronExpression() {
    const cronExp = this.generateCronExpression();
    $("#cronExpression").val(cronExp);
    $("#cronModal").modal("hide");
    this.trigger("cron:selected", { cron: cronExp });
  }

  // Event handler for manual input of the cron expression
  manualInput() {
    this.parseCronExpression($("#cronExpression").val());
  }

  // Event handler when modal is opened
  openModal() {
    this.parseCronExpression($("#cronExpression").val());
  }

  // Reset all form elements (helper function)
  resetForm() {
    $("select").prop("selectedIndex", 0);
    $('#weekly input[type="checkbox"]')
      .prop("checked", false)
      .closest(".btn")
      .removeClass("active");
  }

  // Event handler when cron expression is deleted
  deleteCron() {
    $("#confirmDeleteModal").modal("hide");
    $("#cronExpression").val("");
    this.trigger("cron:selected", { cron: "" });
  }
}

// Instantiate the view in the main entry file
//import CronView from "./CronView.js";
//const cronView = new CronView();
