(() => {
  const KEY = 'reversex_fixture_tasks_v1';
  const input = document.getElementById('task-name');
  const form = document.getElementById('task-form');
  const error = document.getElementById('error');
  const list = document.getElementById('task-list');
  const empty = document.getElementById('empty');

  function load() {
    try { const value = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(value) ? value.filter(v => typeof v === 'string') : []; }
    catch { return []; }
  }
  let tasks = load();
  function render() {
    list.replaceChildren();
    for (const task of tasks) { const item = document.createElement('li'); item.textContent = task; list.appendChild(item); }
    empty.hidden = tasks.length > 0;
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const task = input.value.trim();
    if (!task) { error.textContent = 'Task name is required.'; return; }
    if (task.length > 80) { error.textContent = 'Task name must be 80 characters or fewer.'; return; }
    error.textContent = '';
    tasks.push(task);
    localStorage.setItem(KEY, JSON.stringify(tasks));
    input.value = '';
    render();
  });
  render();
})();
