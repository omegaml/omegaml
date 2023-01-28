$(document).ready(function () {
  $("#list-table").DataTable();
  $("#logviewer").DataTable({
    ajax: "/runtime/log",
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
      { data: "text", width: "80%" },
      { data: "level" },
      { data: "hostname" },
      { data: "userid" },
      { data: "logger" },
    ],
  });
  $(".worker-item").click(function () {
    var workerId = $(this).attr("worker-id");
    console.log(workerId);
    $("#worker-modal").modal("show");
  });
  $("#worker-modal").on("shown.bs.modal", function (e) {
    var workerId = $(e.relatedTarget).attr("worker-id");
    console.log(workerId);
    $.ajax({
      url: "/runtime/worker/" + workerId,
      success: function (data) {
        $("#worker-modal .modal-title").text(data.id);
        $("#worker-modal .modal-body").html(data);
      },
    });
  });
});
