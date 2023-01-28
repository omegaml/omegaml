$(document).ready(function () {
  // plot status data
  function plotchart(el, url) {
    $.ajax({
      dataType: "json",
      url: url,
      success: function (data) {
        $(el).show();
        Plotly.newPlot($(el)[0], data, {});
      },
    });
  }
  plotchart("#status-chart", "/runtime/status/plot/health");
  plotchart("#uptime-chart", "/runtime/status/plot/uptime");
  $("#database-tab").on("shown.bs.tab", function (e) {
    plotchart("#dbstats-chart", "/runtime/database/dbstats/plot");
    plotchart("#repostats-chart", "/runtime/database/repostats/plot");
  });
});
