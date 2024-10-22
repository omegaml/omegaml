import DateRangeView from "../../widgets/sincepick.js";
import PaginatedRunGridView from "../../widgets/pagedcards.js";

$(function () {
  $("#experiments-tab").on("shown.bs.tab", function (e) {
    // since/date range picker
    const dateRangeView = new DateRangeView({
      el: "#exp-sinceRangePicker",
      events: {
        "since:selected": function (event, data) {
          console.log("since:selected", data);
          var exp = $("#dropdownExperiments").text();
          showTable(exp);
        },
        "range:selected": function (event, data) {
          console.log("range:selected", data);
        },
      },
    });
    dateRangeView.render();
    // cards view
    const gridView = new PaginatedRunGridView({
      el: "#expcards",
    });
    // query experiment data and show as a table
    function initializeTable(headers, exp, since, end) {
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
        select: true,
        pageLength: 5,
        layout: {
          topEnd: "paging",
        },
        ajax: {
          url: `/tracking/experiment/data/${exp}?&since=${since}&end=${end}&summary=1`,
          type: "GET",
        },
        columns: columns,
      });
    }

    function showRunCards(exp) {
      const since = dateRangeView.model.get("startDate");
      const end = dateRangeView.model.get("endDate");
      gridView.collection.url = `/tracking/experiment/data/${exp}?&since=${since}&end=${end}&summary=1`;
      gridView.collection.fetch({ reset: true });
      gridView.render();
    }

    function showTable(exp) {
      $("#expchart").hide();
      $("#exptable").show();
      $("#dropdownExperiments").text(exp);
      const since = dateRangeView.model.get("startDate");
      const end = dateRangeView.model.get("endDate");
      $.ajax({
        url: `/tracking/experiment/data/${exp}?initialize=1&summary=1&since=${since}&end=${end}`,
        type: "GET",
        success: function (json) {
          var headers = json.columns || Object.keys(json.data[0]);
          var thead = "<thead><tr>";
          headers.forEach(function (header) {
            thead += "<th>" + header + "</th>";
          });
          thead += "</tr></thead>";
          $("#expviewer").html(thead);
          initializeTable(headers, exp, since, end);
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
    function plotchart(exp, since, end, multi = false) {
      var multi = multi ? 1 : 0;
      var selected = $("#expviewer")
        .DataTable({ retrieve: true })
        .rows({ selected: true })
        .data()
        .toArray();
      selected = selected.map((row) => row.run);
      $.ajax({
        dataType: "json",
        url: `/tracking/experiment/plot/${exp}?multicharts=${multi}&since=${since}&end=${end}&runs=${selected}`,
        success: function (data) {
          $("#exptable").hide();
          $("#expchart").show();
          Plotly.newPlot("expchart", data, {});
        },
      });
    }
    $("#plotchart").on("click", function () {
      var exp = $("#dropdownExperiments").text();
      var since = dateRangeView.model.get("startDate");
      var end = dateRangeView.model.get("endDate");
      plotchart(exp, since, end, false);
    });
    $("#multicharts").on("click", function () {
      var exp = $("#dropdownExperiments").text();
      var since = dateRangeView.model.get("startDate");
      var end = dateRangeView.model.get("endDate");
      plotchart(exp, since, end, true);
    });
  });
  $("#monitoring-tab").on("shown.bs.tab", function (e) {
    // since/date range picker
    const dateRangeView = new DateRangeView({
      el: "#mon-sinceRangePicker",
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
    dateRangeView.render();
    plotmonitor({
      model: metadata.name,
      column: null,
      since: null,
    });
    $(".mon.refresh").trigger("click");
  });
});
