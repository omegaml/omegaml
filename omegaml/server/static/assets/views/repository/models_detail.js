import DateRangeView from "../../widgets/sincepick.js";

$(function () {
  // query experiment data and show as a table
  function initializeTable(headers) {
    // https://datatables.net/forums/discussion/79217
    var columns = headers.map(function (header) {
      return { data: header, title: header };
    });
    $("#expviewer").DataTable({
      destroy: true, // remove previuos table, recreate it
      processing: true,
      serverSide: true,
      responsive: true,
      paging: true,
      ajax: {
        url: "/tracking/experiment/data/d-reg-0",
        type: "GET",
      },
      columns: columns,
    });
  }

  function showTable(exp) {
    $("#expchart").hide();
    $("#exptable").show();
    $("#dropdownExperiments").text(exp);
    $.ajax({
      url: "/tracking/experiment/data/d-reg-0?initialize=1",
      type: "GET",
      success: function (json) {
        var headers = json.columns || Object.keys(json.data[0]);
        var thead = "<thead><tr>";
        headers.forEach(function (header) {
          thead += "<th>" + header + "</th>";
        });
        thead += "</tr></thead>";
        $("#expviewer").html(thead);
        initializeTable(headers);
      },
    });
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
