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
    plotchart("#uptime-chart", "/runtime/status/plot/uptime");
  }
  function showservicestatus() {
    $("#status-chart").load("/runtime/status?title=false", function () {
      $("#status-chart .collapse").collapse({
        toggle: false, // Ensures collapse is properly initialized but doesn't auto-toggle
      });
      $("#status-chart .card-header").on("click", function () {
        $(this).next(".collapse").collapse("toggle");
      });
    });
  }
  $("#summary-tab").on("shown.bs.tab", function (e) {
    refresh();
  });
  $("#database-tab").on("shown.bs.tab", function (e) {
    plotchart("#dbstats-chart", "/runtime/database/dbstats/plot");
    plotchart("#repostats-chart", "/runtime/database/repostats/plot");
  });
  // initial and autorefresh
  setInterval(function () {
    refresh();
  }, 10000);
  refresh();
});
