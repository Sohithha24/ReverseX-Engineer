(function () {
  const a = document.getElementById('num-a');
  const b = document.getElementById('num-b');
  const message = document.getElementById('message');
  const result = document.getElementById('result');
  const addBtn = document.getElementById('btn-add');
  const subBtn = document.getElementById('btn-sub');
  const resetBtn = document.getElementById('btn-reset');

  function clearOutcome() {
    message.textContent = '';
    result.textContent = '';
  }

  function parseOperand(raw) {
    const text = String(raw ?? '').trim();
    if (text === '') return { ok: false, reason: 'empty' };
    const value = Number(text);
    if (!Number.isFinite(value)) return { ok: false, reason: 'nan' };
    return { ok: true, value };
  }

  function compute(op) {
    const left = parseOperand(a.value);
    const right = parseOperand(b.value);
    if (!left.ok || !right.ok) {
      result.textContent = '';
      message.textContent = 'Both numbers are required.';
      return;
    }
    message.textContent = '';
    const value = op === 'add' ? left.value + right.value : left.value - right.value;
    result.textContent = String(value);
  }

  addBtn.addEventListener('click', function () { compute('add'); });
  subBtn.addEventListener('click', function () { compute('sub'); });
  resetBtn.addEventListener('click', function () {
    a.value = '';
    b.value = '';
    clearOutcome();
  });
})();
