(function () {
  var form = document.getElementById("task-form");
  var input = document.getElementById("task-name");
  var error = document.getElementById("error");
  var emptyState = document.getElementById("empty-state");
  var list = document.getElementById("task-list");
  var STORAGE_KEY = "taskboard.tasks";

  function loadTasks() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.filter(function (t) { return typeof t === "string"; });
      }
      return [];
    } catch (e) {
      return [];
    }
  }

  function saveTasks(tasks) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    } catch (e) {}
  }

  var tasks = loadTasks();

  function render() {
    list.textContent = "";
    tasks.forEach(function (name) {
      var li = document.createElement("li");
      li.textContent = name;
      list.appendChild(li);
    });
    if (tasks.length === 0) {
      emptyState.hidden = false;
    } else {
      emptyState.hidden = true;
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var rawValue = input.value;
    var name = rawValue == null ? "" : String(rawValue).trim();
    if (!name) {
      error.hidden = false;
      // Keep empty-state visible when there are no tasks
      render();
      error.hidden = false;
      input.focus();
      return;
    }
    error.hidden = true;
    tasks.push(name);
    saveTasks(tasks);
    render();
    input.value = "";
    input.focus();
  });

  input.addEventListener("input", function () {
    var v = input.value == null ? "" : String(input.value).trim();
    if (v) {
      error.hidden = true;
    }
  });

  error.hidden = true;
  render();
})();
