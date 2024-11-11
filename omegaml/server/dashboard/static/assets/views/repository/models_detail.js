import DateRangeView from "../../widgets/sincepick.js";
import PaginatedRunGridView from "../../widgets/pagedcards.js";

$(function () {
  $("#experiments-tab").on("shown.bs.tab", function (e) {
    // since/date range picker
    const dateRangeView = new DateRangeView({
      el: "#exp-sinceRangePicker",
      events: {
        "since:selected": function (event, data) {
          console.debug("since:selected", data);
          var exp = $("#dropdownExperiments").text();
          showTable(exp);
        },
        "range:selected": function (event, data) {
          console.debug("range:selected", data);
        },
      },
    });
    dateRangeView.render();
    // cards view
    const gridView = new PaginatedRunGridView({
      el: "#expcards",
    });
    // query experiment data and show as a table
    function initializeTable(headers, exp, since, end, runs) {
      // https://datatables.net/forums/discussion/79217
      var columns = headers.map(function (header) {
        return { data: header, title: header };
      });
      var summary = runs ? 0 : 1;
      var datatable = $("#expviewer").DataTable({
        destroy: true, // remove previuos table, recreate it
        processing: true,
        serverSide: true,
        responsive: true,
        paging: true,
        select: true,
        pageLength: 50,
        layout: {
          topEnd: "paging",
        },
        ajax: {
          url:
            url_for("omega-server.tracking_api_experiment_data", {
              name: exp,
            }) + `?&since=${since}&end=${end}&summary=${summary}&run=${runs}`,
          type: "GET",
        },
        columns: columns,
      });
    }
    function showRunCards(exp) {
      const since = dateRangeView.model.get("startDate");
      const end = dateRangeView.model.get("endDate");
      gridView.collection.url =
        url_for("omega-server.tracking_api_experiment_data", {
          name: exp,
        }) + `?&since=${since}&end=${end}&summary=1`;
      gridView.collection.fetch({ reset: true });
      gridView.render();
    }
    function showTable(exp, recreate = false, runs) {
      $("#expchart").hide();
      $("#exptable").show();
      $("#dropdownExperiments").text(exp) || "Experiment";
      const since = dateRangeView.model.get("startDate");
      const end = dateRangeView.model.get("endDate");
      const summary = runs ? 0 : 1;
      $.ajax({
        url:
          url_for("omega-server.tracking_api_experiment_data", {
            name: exp,
          }) + `?initialize=1&summary=${summary}&since=${since}&end=${end}`,
        type: "GET",
        success: function (json) {
          $("#expviewer").DataTable().destroy();
          var headers = json.columns || Object.keys(json.data[0]);
          var thead = "<thead><tr>";
          headers.forEach(function (header) {
            thead += "<th>" + header + "</th>";
          });
          thead += "</tr></thead>";
          $("#expviewer").html(thead);
          initializeTable(headers, exp, since, end, runs);
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
    $("#details").on("click", function () {
      var datatable = $("#expviewer").DataTable({
        retrieve: true,
      });
      var exp = $("#dropdownExperiments").text();
      var selected = datatable.rows({ selected: true }).data().toArray();
      selected = selected.map((row) => row.run);
      showTable(exp, true, selected);
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
        url:
          url_for("omega-server.tracking_api_plot_metrics", { name: exp }) +
          `?multicharts=${multi}&since=${since}&end=${end}&run=${selected}`,
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
    showTable("Experiment", true);
  });
  $("#monitoring-tab").on("shown.bs.tab", function (e) {
    // since/date range picker
    const dateRangeView = new DateRangeView({
      el: "#mon-sinceRangePicker",
      events: {
        "since:selected": function (event, data) {
          console.debug("since:selected", data);
          refreshMonitor();
        },
        "range:selected": function (event, data) {
          console.debug("range:selected", data);
        },
      },
    });
    // plot monitor charts
    function plotmonitor({ model, column, since, kind, stats }) {
      $.ajax({
        dataType: "json",
        url:
          url_for("omega-server.tracking_api_plot_monitor", { model: model }) +
          `?column=${column}&since=${since}&kind=${kind}&stats=${stats}`,
        success: function (data) {
          if (data.image) {
            $("#monplot").attr("src", "data:image/png;base64," + data.image);
          } else {
            console.error("Image data is missing");
          }
        },
        error: function (xhr, status, error) {
          console.error("Error: " + xhr.responseText);
        },
      });
    }
    function refreshMonitor() {
      const model = metadata.name;
      $.ajax({
        dataType: "json",
        url: url_for("omega-server.tracking_api_compare_monitor", {
          model: model,
        }),
        success: function (data) {
          var columns = data.summary.columns;
          var stats = data.stats;
          var snapshots = data.snapshots;
          // set up drop down for columns
          var dropdown = $(".dropdown-menu.mon.column.items");
          dropdown.empty();
          dropdown.append(
            `<a class="dropdown-item mon column refresh" href="#">(reset)</a>`
          );
          if (!columns || Object.keys(columns).length === 0) {
            console.error("No columns available");
            return;
          }
          Object.keys(columns).forEach((col) => {
            dropdown.append(
              `<a class="dropdown-item mon column" href="#">${col}</a>`
            );
          });
          // set up drop down for statistics
          var dropdown = $(".dropdown-menu.mon.stats.items");
          dropdown.empty();
          dropdown.append(
            `<a class="dropdown-item mon stats refresh" href="#">(reset)</a>`
          );
          if (!stats || Object.keys(stats).length === 0) {
            console.error("No stats available");
            return;
          }
          stats.forEach((col) => {
            dropdown.append(
              `<a class="dropdown-item mon stats" href="#">${col}</a>`
            );
          });
          // handlers
          $(".dropdown-item.mon").on("click", function () {
            var value = $(this).text();
            if (value === "(reset)") {
              value = $(this)
                .closest(".dropdown")
                .find(".dropdown-toggle")
                .data("default");
            }
            $(this).closest(".dropdown").find(".dropdown-toggle").text(value);
            refresh_plot();
          });
          // refresh plot
          function refresh_plot() {
            var column = $("#dropdownDriftColumns").text().trim();
            var stat = $("#dropdownStatistics").text().trim();
            $("#dropdownDriftColumns").text(column);
            plotmonitor({
              model: model,
              column: column != "Columns" ? column : null,
              since: dateRangeView.model.get("startDate"),
              stats: stat != "Statistics" ? stat : null,
              kind: null,
            });
          }
          $(".mon.column.refresh").on("click", function () {
            $("#dropdownDriftColumns").text("Columns");
            refresh_plot();
          });
          $(".mon.stats.refresh").on("click", function () {
            $("#dropdownStatistics").text("Statistics");
            refresh_plot();
          });
          // show snapshots
          // Mapping of status to Font Awesome icons
          const statusIcons = {
            alert: '<i class="fas fa-exclamation-triangle text-danger"></i>',
            warning: '<i class="fas fa-exclamation-circle text-warning"></i>',
            stable: '<i class="fas fa-check-circle text-success"></i>',
            unknown: '<i class="fas fa-question-circle text-secondary"></i>',
          };
          function populateSnapshotsList(snapshots) {
            const list = $("#snapshotsList");
            list.empty();
            snapshots.forEach((snapshot) => {
              const statusClass = {
                stable: "text-success",
                warning: "text-warning",
                alert: "text-danger",
              }[snapshot.status];
              snapshot.dt_from = new Date(snapshot.dt_from).toLocaleString();
              const item = $(`
              <div class="snapshot-item" data-id="${snapshot.id}">
                  <div class="d-flex justify-content-between">
                      <strong>${snapshot.dt_from} [${snapshot.seq_from}:${
                snapshot.seq_to
              }]</strong>
                      <span class="${statusClass}">
                         ${
                           statusIcons[snapshot.status] ||
                           statusIcons["unknown"]
                         }
                      </span>
                  </div>
                  <div class="small text-muted">
                    ${snapshot.column} (${
                snapshot.stats
              }: ${snapshot.metric.toFixed(3)},&nbsp; 
              score: ${snapshot.score.toFixed(2)})
                  </div>
              </div>`);
              list.append(item);
            });
          }
          // snapshot data
          populateSnapshotsList(snapshots);
          // Handle snapshot selection
          $("#snapshotsList").on("click", ".snapshot-item", function () {
            $(".snapshot-item").removeClass("active");
            $(this).addClass("active");
            // Here you would typically load detailed data for the selected snapshot
          });
          // Handle refresh button
          $("#refreshBtn").on("click", function () {
            // Here you would typically fetch new data from the server
            populateSnapshotsList(sampleData.snapshots);
            updateChart(sampleData.snapshots);
          });
        },
      });
      plotmonitor({
        model: metadata.name,
        column: null,
        since: null,
        stats: null,
      });
    }
    $(".mon.refresh").on("click", function (event, data) {
      refreshMonitor();
    });
    $("#plotmon-dist").on("click", function (event, data) {
      var column = $("#dropdownDriftColumns").text().trim();
      var stats = $("#dropdownStatistics").text().trim();
      plotmonitor({
        model: metadata.name,
        column: column != "Columns" ? column : null,
        since: dateRangeView.model.get("startDate"),
        kind: "dist",
        stats: stats != "Statistics" ? stats : null,
      });
    });
    $("#plotmon-time").on("click", function (event, data) {
      var column = $("#dropdownDriftColumns").text().trim();
      var stats = $("#dropdownStatistics").text().trim();
      plotmonitor({
        model: metadata.name,
        column: column != "Columns" ? column : null,
        since: dateRangeView.model.get("startDate"),
        kind: "time",
        stats: stats != "Statistics" ? stats : null,
      });
    });
    dateRangeView.render();
    refreshMonitor();
  });
});
