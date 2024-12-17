import CronView from "../../widgets/cronpick.js";

// server rendered variables
$(function () {
  var resultsViewer = null;
  var scheduleViewer = null;
  const context = window.context;
  // build experiment data viewer on showing tab
  $("#results-tab").on("shown.bs.tab", function (e) {
    resultsViewer ? resultsViewer.ajax.reload() : null;
    resultsViewer = $("#results-viewer").DataTable({
      ajax: url_for("omega-server.jobs_api_list_runs", {
        name: context.name,
      }),
      retrieve: true, // if already initialized, return the instance
      serverSide: true,
      search: {
        return: true,
      },
      processing: true,
      responsive: true,
      //scrollX: true,
      language: {
        emptyTable: "no data",
      },
      columns: [
        {
          data: "results",
          render: function (data, type, row, meta) {
            const result_url = url_for("omega-server.jobs_api_get_results", {
              name: data.replace("results/", ""),
            });
            return `<a class="job-result" result-url="${result_url}" href="${result_url}">${data}</a>`;
          },
        },
        { data: "ts" },
        { data: "status" },
      ],
    });
    resultsViewer.ajax.reload(function (data) {
      // install click handler for job result links
      setInterval(function () {
        $(".job-result").click(function (e) {
          e.preventDefault();
          var result_url = $(e.target).attr("result-url");
          if (e.shiftKey) {
            window.open(result_url, "_blank");
          } else {
            $("#jobview-modal").attr("result-url", result_url);
            $("#jobview-modal").modal("show");
          }
        });
      }, 100);
    }, false);
  });
  // load job results into modal
  $("#jobview-modal").on("shown.bs.modal", function (e) {
    var result_url = $(e.target).attr("result-url");
    $("#jobview-modal .modal-body iframe").attr("src", result_url);
    $("#jobview-modal .modal-title").html(
      '<a href="' + result_url + '" target=blank>Job Results</a>'
    );
  });
  $("#jobview-modal").on("hidden.bs.modal", function (e) {
    $("#jobview-modal .modal-body iframe").attr("src", "");
    $("#jobview-modal .modal-title").text("");
  });
  $("#schedule-tab").on("shown.bs.tab", function (e) {
    const cronView = new CronView({
      el: "#cronContainer",
      cronExpression: context.schedule.cron,
      events: {
        "cron:selected": function (event, data) {
          $.ajax({
            url: url_for("omega-server.jobs_api_set_schedule", {
              name: context.name,
            }),
            type: "POST",
            data: JSON.stringify({
              cron: data.cron,
            }),
            contentType: "application/json",
            dataType: "json",
          })
            .done(function (data) {
              scheduleViewer.ajax.reload();
            })
            .fail(function (data) {
              console.error("error", data);
            });
        },
      },
    });
    cronView.render();
    scheduleViewer ? scheduleViewer.ajax.reload() : null;
    scheduleViewer = $("#schedule-viewer").DataTable({
      retrieve: true, // if already initialized, return the instance
      ajax: {
        url: url_for("omega-server.jobs_api_get_schedule", {
          name: context.name,
        }),
        dataSrc: function (data) {
          console.debug("schedule data", data);
          return data.data.triggers;
        },
      },
      search: {
        return: true,
      },
      processing: true,
      responsive: true,
      //scrollX: true,
      columns: [
        { data: "event" },
        { data: "event-kind" },
        { data: "run-at" },
        { data: "status" },
      ],
    }); // DataTable
  }); // shown.bs.tab
});
