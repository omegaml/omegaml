import DateRangeView from "../../widgets/sincepick.js";

$(function () {
  // since/date range picker
  const dateRangeView = new DateRangeView({
    el: "#sinceRangePicker",
    events: {
      "since:selected": function (event, data) {
        console.log("since:selected", data);
        plotmonitor({
          model: metadata.name,
          column: null,
          since: data.startDate,
        });
      },
      "range:selected": function (event, data) {
        console.log("range:selected", data);
      },
    },
  });
  // plot monitor charts
  function plotmonitor({ model, column, since }) {
    $.ajax({
      dataType: "json",
      url: `/tracking/monitor/plot/${model}?column=${column}&since=${since}`,
      success: function (data) {
        $("#monplot").attr("src", "data:image/png;base64," + data["image"]);
      },
      error: function (xhr, status, error) {
        alert("Error: " + xhr.responseText);
        dateRangeView.initializeDates();
        plotmonitor({ model: model, column: null, since: null });
      },
    });
  }
  $(".mon.refresh").on("click", function (event, data) {
    const model = metadata.name;
    $.ajax({
      dataType: "json",
      url: `/tracking/monitor/compare/${model}`,
      success: function (data) {
        var columns = data.columns;
        var dropdown = $(".dropdown-menu.mon.column.items");
        dropdown.empty();
        dropdown.append(
          `<a class="dropdown-item mon reset" href="#">(reset)</a>`
        );
        Object.keys(columns).forEach((col) => {
          dropdown.append(
            `<a class="dropdown-item mon column" href="#">${col}</a>`
          );
        });
        $(".dropdown-item.mon.column").on("click", function () {
          plotmonitor({
            model: model,
            column: $(this).text(),
            since: dateRangeView.model.get("startDate"),
          });
        });
        $(".mon.reset").on("click", function () {
          plotmonitor({
            model: model,
            column: null,
            since: dateRangeView.model.get("startDate"),
          });
        });
      },
    });
  });
  $("#plotmonitor").on("click", function (event, data) {
    plotmonitor({
      model: metadata.name,
      column: null,
      since: dateRangeView.model.get("startDate"),
    });
  });
  $("#monitoring-tab").on("shown.bs.tab", function (e) {
    dateRangeView.render();
    plotmonitor({
      model: metadata.name,
      column: null,
      since: null,
    });
    $(".mon.refresh").trigger("click");
  });
});
