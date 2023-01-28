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
  //plotchart("#worker-status-chart", "/runtime/worker/plot/load");
});
