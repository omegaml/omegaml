$(document).ready(function () {
  // plot status data
  function plotchart(el, url) {
    $.ajax({
      dataType: "json",
      url: url,
      success: function (data) {
        $(el).show();
        const layout = { showlegend: false };
        const config = { displayModeBar: false };
        Plotly.newPlot($(el)[0], data, layout, config).then(function () {
          $("#uptime-chart .modebar-container").hide();
        });
      },
    });
  }
  // show service status
  function refresh() {
    showservicestatus();
    plotchart(
      "#uptime-chart",
      url_for("omega-server.runtime_api_status_plot_uptime")
    );
  }
  function showservicestatus() {
    $("#status-chart").load(
      url_for("omega-server.runtime_status") + "?title=false",
      function () {
        $("#status-chart .collapse").collapse({
          toggle: false, // Ensures collapse is properly initialized but doesn't auto-toggle
        });
        $("#status-chart .card-header").on("click", function () {
          $(this).next(".collapse").collapse("toggle");
        });
      }
    );
  }
  $("#summary-tab").on("shown.bs.tab", function (e) {
    refresh();
  });
  $("#database-tab").on("shown.bs.tab", function (e) {
    plotchart(
      "#dbstats-chart",
      url_for("omega-server.runtime_api_runtime_dbstats_plot")
    );
    plotchart(
      "#repostats-chart",
      url_for("omega-server.runtime_api_runtime_repostats_plot")
    );
  });
  // initial and autorefresh
  setInterval(function () {
    refresh();
  }, 10000);
  refresh();
});
