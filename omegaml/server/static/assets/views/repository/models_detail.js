import DateRangeView from "../../widgets/sincepick.js";

$(function () {
  // build experiment data viewer
  var expViewer = $("#expviewer").DataTable({
    ajax: `/tracking/experiment/data/.empty`,
    dom:
      "<'row'<'col-sm-12 col-md-6'l><'col-sm-12 col-md-6'fp>>" +
      "<'row'<'col-sm-12'tr>>" +
      "<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",
    serverSide: true,
    search: {
      return: true,
    },
    processing: true,
    responsive: true,
    //scrollX: true,
    columns: [
      { data: "run" },
      { data: "event" },
      { data: "step" },
      { data: "key" },
      { data: "value" },
      { data: "dt" },
    ],
  });
  // query experiment data and show as a table
  function showTable(exp) {
    $("#expchart").hide();
    $("#exptable").show();
    expViewer.ajax.url(`/tracking/experiment/data/${exp}`).load();
    $("#dropdownExperiments").text(exp);
  }
  $(".dropdown-item.exp").on("click", function () {
    var exp = $(this).text();
    showTable(exp);
  });
  $("#showtable").on("click", function () {
    var exp = $("#dropdownExperiments").text();
    showTable(exp);
  });
  // plot experiment data
  function plotchart(exp, multi = false) {
    var multi = multi ? 1 : 0;
    $.ajax({
      dataType: "json",
      url: `/tracking/experiment/plot/${exp}?multicharts=${multi}`,
      success: function (data) {
        $("#exptable").hide();
        $("#expchart").show();
        Plotly.newPlot("expchart", data, {});
      },
    });
  }
  $("#plotchart").on("click", function () {
    var exp = $("#dropdownExperiments").text();
    plotchart(exp, false);
  });
  $("#multicharts").on("click", function () {
    var exp = $("#dropdownExperiments").text();
    plotchart(exp, true);
  });
  // plot monitor charts
  function plotmonitor(model, column) {
    $.ajax({
      dataType: "json",
      url: `/tracking/monitor/plot/${model}?column=${column}`,
      success: function (data) {
        $("#monplot").attr("src", "data:image/png;base64," + data["image"]);
      },
    });
  }
  $(".mon.refresh").on("click", function () {
    var model = metadata.name;
    $.ajax({
      dataType: "json",
      url: `/tracking/monitor/compare/${model}`,
      success: function (data) {
        var columns = data.columns;
        var dropdown = $(".dropdown-menu.mon.column.items");
        dropdown.empty();
        Object.keys(columns).forEach((col) => {
          dropdown.append(
            `<a class="dropdown-item mon column" href="#">${col}</a>`
          );
        });
        $(".dropdown-item.mon.column").on("click", function () {
          var column = $(this).text();
          var model = metadata.name;
          plotmonitor(model, column);
        });
      },
    });
  });
  $("#plotmonitor").on("click", function () {
    var column = $("#dropdownDriftColumns").text();
    var model = metadata.name;
    plotmonitor(model);
  });
  $("#monitoring-tab").on("shown.bs.tab", function (e) {
    // Instantiate the view, rendering it into a container
    const dateRangeView = new DateRangeView({
      el: "#sinceRangePicker",
    });
    dateRangeView.render();
  });
});
