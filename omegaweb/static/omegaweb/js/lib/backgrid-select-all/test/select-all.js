/*
  backgrid
  http://github.com/wyuenho/backgrid

  Copyright (c) 2013 Jimmy Yuen Ho Wong and contributors
  Licensed under the MIT @license.
*/
describe("A SelectRowCell", function () {

  var collection;
  var model;
  var cell;

  beforeEach(function () {
    model = new Backbone.Model();
    collection = new Backbone.Collection();
    collection.add(model);

    cell = new Backgrid.Extension.SelectRowCell({
      model: model,
      column: {
        name: "",
        cell: "select-row"
      }
    });

    cell.render();
  });

  it("renders a renderable cell", function () {
    expect(cell.$el.hasClass("renderable")).toBe(true);
  });

  it("renders a checkbox", function () {
    expect(cell.$el.find(":checkbox").length).toBe(1);
  });

  it("triggers a Backbone `backgrid:selected` event when the checkbox is checked", function () {
    var selectedTriggered = false;
    model.on("backgrid:selected", function () {
      selectedTriggered = true;
    });
    cell.$el.find(":checkbox").prop("checked", true).change();
    expect(selectedTriggered).toBe(true);
  });

  it("checks or unchecks its checkbox when the model triggers a Backbone `backgrid:select` event", function () {
    model.trigger("backgrid:select", model, true);
    expect(cell.$el.find(":checkbox").prop("checked")).toBe(true);
    model.trigger("backgrid:select", model, false);
    expect(cell.$el.find(":checkbox").prop("checked")).toBe(false);
  });

  it("toggles a `selected` class on the parent row when the checkbox changes", function () {
    var $row = $('<tr></tr>');
    $row.append(cell.$el);
    cell.$el.find(":checkbox").prop("checked", true).change();
    expect($row.hasClass("selected")).toBe(true);
    cell.$el.find(":checkbox").prop("checked", false).change();
    expect($row.hasClass("selected")).toBe(false);
  });

});

describe("A SelectAllHeaderCell", function () {

  describe("when using a plain backbone collection", function () {
    var collection;
    var cell;

    beforeEach(function () {
      collection = new Backbone.Collection([{id: 1}, {id: 2}]);
      cell = new Backgrid.Extension.SelectAllHeaderCell({
        collection: collection,
        column: {
          headerCell: "select-all",
          cell: "select-row",
          name: ""
        }
      });

      cell.render();
    });

    it("renders a renderable header cell", function () {
      expect(cell.$el.hasClass("renderable")).toBe(true);
    });

    it("triggers a `backgrid:select` event on each model and a `backgrid:select-all` event on the collection when its checkbox is checked", function () {
      var selectTriggerArgs = [];
      collection.on("backgrid:select", function () {
        selectTriggerArgs.push(Array.prototype.slice.apply(arguments));
      });

      var selectAllTriggerArgs = [];
      collection.on("backgrid:select-all", function () {
        selectAllTriggerArgs.push(Array.prototype.slice.apply(arguments));
      });

      cell.$el.find(":checkbox").prop("checked", true).change();
      expect(selectTriggerArgs.length).toBe(2);
      expect(selectTriggerArgs[0][0]).toBe(collection.at(0));
      expect(selectTriggerArgs[0][1]).toBe(true);
      expect(selectTriggerArgs[1][0]).toBe(collection.at(1));
      expect(selectTriggerArgs[1][1]).toBe(true);
      expect(selectAllTriggerArgs.length).toBe(1);
      expect(selectAllTriggerArgs[0][0]).toBe(collection);
      expect(selectAllTriggerArgs[0][1]).toBe(true);
    });

    it("unchecks itself when a model triggers a `backgrid:selected` event with a false value", function () {
      cell.$el.find(":checkbox").prop("checked", true).change();
      collection.at(0).trigger("backgrid:selected", collection.at(0), false);
      expect(cell.$el.find(":checkbox").prop("checked")).toBe(false);
    });

    it("unchecks itself when the collection becomes empty during removals", function () {
      cell.$el.find(":checkbox").prop("checked", true).change();
      while (collection.length) collection.remove(collection.first());
      expect(cell.$el.find(":checkbox").prop("checked")).toBe(false);
    });

    it("unchecks itself when the collection becomes empty after a `backgrid:refresh`", function () {
      cell.$el.find(":checkbox").prop("checked", true).change();
      collection.reset();
      collection.trigger("backgrid:refresh");
      expect(cell.$el.find(":checkbox").prop("checked")).toBe(false);
    });

    it("will trigger a `backgrid:select` event on all models after a `backgrid:refresh` event if checked", function () {
      var selectedIds = {};
      collection.on("backgrid:select", function (model) {
        selectedIds[model.id] = true;
      });
      cell.$el.find(":checkbox").prop("checked", true).change();
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(2);
      expect("1" in selectedIds).toBe(true);
      expect("2" in selectedIds).toBe(true);

      collection.reset([{id: 3}, {id: 4}]);
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(4);
      expect("1" in selectedIds).toBe(true);
      expect("2" in selectedIds).toBe(true);
      expect("3" in selectedIds).toBe(true);
      expect("4" in selectedIds).toBe(true);
    });

    it("will trigger a `backgrid:select` event on each previously selected model after a `backgrid:refresh` event", function () {
      var selectedIds = {};
      collection.on("backgrid:select", function (model) {
        selectedIds[model.id] = true;
      });
      collection.last().trigger("backgrid:selected", collection.last(), true);
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(1);
      expect("2" in selectedIds).toBe(true);
    });

    it("will dereference a model from selectedModels if it is removed from the underlying collection", function () {
      var model = collection.at(0);
      model.trigger("backgrid:selected", model, true);
      expect(model.id in cell.selectedModels).toBe(true);
      collection.remove(model);
      expect(model.id in cell.selectedModels).toBe(false);
      expect(_.size(cell.selectedModels)).toBe(0);
    });

    it("will automatically select itself when all rows are selected", function () {
      for(var i = 0; i < collection.length; i++){
        collection.at(i).trigger("backgrid:selected", collection.at(i), true);
      }
      expect(cell.checkbox().prop("checked")).toBe(true);
    });

  });

  describe("when using a Backbone.PageableCollection unders server mode", function () {
    var collection;
    var cell;

    beforeEach(function () {
      collection = new Backbone.PageableCollection([{id: 1}, {id: 2}], {
        state: {
          pageSize: 2
        }
      });
      cell = new Backgrid.Extension.SelectAllHeaderCell({
        collection: collection,
        column: {
          headerCell: "select-all",
          cell: "select-row",
          name: ""
        }
      });

      cell.render();
    });

    it("will trigger a `backgrid:select` event on all models after a `backgrid:refresh` event if checked", function () {
      var selectedIds = {};
      collection.on("backgrid:select", function (model) {
        selectedIds[model.id] = true;
      });
      cell.$el.find(":checkbox").prop("checked", true).change();
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(2);
      expect("1" in selectedIds).toBe(true);
      expect("2" in selectedIds).toBe(true);

      collection.reset([{id: 3}, {id: 4}]);
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(4);
      expect("1" in selectedIds).toBe(true);
      expect("2" in selectedIds).toBe(true);
      expect("3" in selectedIds).toBe(true);
      expect("4" in selectedIds).toBe(true);
    });

    it("will trigger a `backgrid:select` event on each previously selected model after a `backgrid:refresh` event", function () {
      var selectedIds = {};
      collection.on("backgrid:select", function (model) {
        selectedIds[model.id] = true;
      });
      collection.last().trigger("backgrid:selected", collection.last(), true);
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(1);
      expect("2" in selectedIds).toBe(true);

      collection.reset([{id: 3}, {id: 4}]);
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(1);
      expect("2" in selectedIds).toBe(true);
    });

  });

  describe("when using a Backbone.PageableCollection under client mode", function () {
    var collection;
    var cell;

    beforeEach(function () {
      collection = new Backbone.PageableCollection([{id: 1}, {id: 2}, {id: 3}], {
        state: {
          pageSize: 2
        },
        mode: "client"
      });
      cell = new Backgrid.Extension.SelectAllHeaderCell({
        collection: collection,
        column: {
          headerCell: "select-all",
          cell: "select-row",
          name: ""
        }
      });

      cell.render();
    });

    it("renders a renderable header cell", function () {
      expect(cell.$el.hasClass("renderable")).toBe(true);
    });

    it("triggers a `backgrid:select` event on each model on the current page, a `backgrid:selected` event on the models on other pages, and a `backgrid:select-all` event on the collection", function () {
      var selectTriggerArgs = [];
      collection.fullCollection.on("backgrid:select", function () {
        selectTriggerArgs.push(Array.prototype.slice.apply(arguments));
      });

      var selectedTriggerArgs = [];
      collection.fullCollection.on("backgrid:selected", function () {
        selectedTriggerArgs.push(Array.prototype.slice.apply(arguments));
      });

      var selectAllTriggerArgs = [];
      collection.on("backgrid:select-all", function () {
        selectAllTriggerArgs.push(Array.prototype.slice.apply(arguments));
      });

      cell.$el.find(":checkbox").prop("checked", true).change();
      expect(selectTriggerArgs.length).toBe(2);
      expect(selectTriggerArgs[0][0]).toBe(collection.fullCollection.at(0));
      expect(selectTriggerArgs[0][1]).toBe(true);
      expect(selectTriggerArgs[1][0]).toBe(collection.fullCollection.at(1));
      expect(selectTriggerArgs[1][1]).toBe(true);
      expect(selectedTriggerArgs.length).toBe(1);
      expect(selectedTriggerArgs[0][0]).toBe(collection.fullCollection.at(2));
      expect(selectedTriggerArgs[0][1]).toBe(true);
      expect(selectAllTriggerArgs.length).toBe(1);
      expect(selectAllTriggerArgs[0][0]).toBe(collection);
      expect(selectAllTriggerArgs[0][1]).toBe(true);
    });

    it("unchecks itself when a model triggers a `backgrid:selected` event with a false value", function () {
      cell.$el.find(":checkbox").prop("checked", true).change();
      collection.fullCollection.last().trigger("backgrid:selected", collection.fullCollection.last(), false);
      expect(cell.$el.find(":checkbox").prop("checked")).toBe(false);
    });

    it("unchecks itself when the collection becomes empty during removals", function () {
      cell.$el.find(":checkbox").prop("checked", true).change();
      while (collection.fullCollection.length) collection.fullCollection.remove(collection.fullCollection.first());
      expect(cell.$el.find(":checkbox").prop("checked")).toBe(false);
    });

    it("unchecks itself when the collection becomes empty after a `backgrid:refresh`", function () {
      cell.$el.find(":checkbox").prop("checked", true).change();
      collection.fullCollection.reset();
      collection.trigger("backgrid:refresh");
      expect(cell.$el.find(":checkbox").prop("checked")).toBe(false);
    });

    it("triggers a `backgrid:select` event on each model on the current page after a `backgrid:refresh` event if checked", function () {
      var selectedIds = {};
      collection.on("backgrid:select", function (model) {
        selectedIds[model.id] = true;
      });
      cell.$el.find(":checkbox").prop("checked", true).change();
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(2);
      expect("1" in selectedIds).toBe(true);
      expect("2" in selectedIds).toBe(true);

      collection.reset([{id: 3}, {id: 4}]);
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(4);
      expect("1" in selectedIds).toBe(true);
      expect("2" in selectedIds).toBe(true);
      expect("3" in selectedIds).toBe(true);
      expect("4" in selectedIds).toBe(true);
    });

    it("will trigger a `backgrid:select` event on each previously selected model after a `backgrid:refresh` event", function () {
      var selectedIds = {};
      collection.fullCollection.on("backgrid:select", function (model) {
        selectedIds[model.id] = true;
      });
      collection.getLastPage();
      collection.last().trigger("backgrid:selected", collection.last(), true);
      collection.trigger("backgrid:refresh");
      collection.getFirstPage();
      collection.trigger("backgrid:refresh");
      expect(_.size(selectedIds)).toBe(1);
      expect("3" in selectedIds).toBe(true);
    });

    it("will dereference a model from selectedModels if it is removed from the underlying collection", function () {
      var model = collection.fullCollection.last();
      model.trigger("backgrid:selected", model, true);
      expect(model.id in cell.selectedModels).toBe(true);
      collection.fullCollection.remove(model);
      expect(model.id in cell.selectedModels).toBe(false);
      expect(_.size(cell.selectedModels)).toBe(0);
    });

    it("unchecking after checking will clear selectedModels", function () {
      cell.$el.find(":checkbox").prop("checked", true).change();
      // this will normally be 3 if the select row cells are in play, but this is correct
      expect(_.size(cell.selectedModels)).toBe(1);
      cell.$el.find(":checkbox").prop("checked", false).change();
      expect(_.size(cell.selectedModels)).toBe(0);
    });

  });

});

describe("Grid#getSelectedModels", function () {

  it("will be attached to Backgrid.Grid's prototype", function () {
    expect(typeof Backgrid.Grid.prototype.getSelectedModels).toBe("function");
  });

  it("will return a list of selected models", function () {
    var collection = new Backbone.Collection([{id: 1}, {id: 2}]);

    var grid = new Backgrid.Grid({
      collection: collection,
      columns: [{
        name: "",
        cell: "select-row",
        headerCell: "select-all"
      }, {
        name: "id",
        cell: "integer"
      }]
    });

    grid.render();

    collection.each(function (model) {
      model.trigger("backgrid:selected", model, true);
    });

    var selectedModels = grid.getSelectedModels();
    expect(selectedModels.length).toBe(2);
    expect(selectedModels[0].id).toBe(1);
    expect(selectedModels[1].id).toBe(2);
  });

  it("will return a list of selected models across pageable pages", function(){
    var pageable = new Backbone.PageableCollection([{id:1}, {id:2}, {id:3}], {
      state: { pageSize: 2 },
      mode: "client"
    });
    var one = pageable.get(1);
    var three = pageable.fullCollection.get(3);

    var grid = new Backgrid.Grid({
      collection: pageable,
      columns: [{
        name: "",
        cell: "select-row",
        headerCell: "select-all"
      }, {
        name: "id",
        cell: "integer"
      }]
    });

    grid.render();

    one.trigger("backgrid:selected", one, true);
    pageable.getLastPage();
    three.trigger("backgrid:selected", three, true);

    var selectedModels = grid.getSelectedModels();

    expect(selectedModels.length).toBe(2);
    expect(selectedModels[0]).toBe(one);
    expect(selectedModels[1]).toBe(three);
  });

});

describe("Grid#clearSelectedModels", function () {

  it("will trigger 'backgrid:select' on all of the selected models with a 'selected' = false", function () {
    var collection = new Backbone.Collection([{id:1}, {id:2}]);

    var grid = new Backgrid.Grid({
      collection: collection,
      columns: [{
        name: "",
        cell: "select-row",
        headerCell: "select-all"
      }, {
        name: "id",
        cell: "integer"
      }]
    });

    grid.render();

    collection.each(function (model) {
      model.trigger("backgrid:selected", model, true);
    });

    var selectedModels = grid.getSelectedModels();
    expect(selectedModels.length).toBe(2);

    grid.clearSelectedModels();

    selectedModels = grid.getSelectedModels();
    expect(selectedModels.length).toBe(0);
  });

});
