(function () {
  const form = document.getElementById('contact-form');
  const nameInput = document.getElementById('name');
  const emailInput = document.getElementById('email');
  const messageInput = document.getElementById('message');
  const status = document.getElementById('status');
  const history = document.getElementById('history');
  const resetBtn = document.getElementById('reset');
  const STORAGE_KEY = 'contactpad-messages-v1';

  function loadMessages() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  }

  function saveMessages(items) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }

  function render() {
    const items = loadMessages();
    history.innerHTML = '';
    items.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = `${item.name} <${item.email}>: ${item.message}`;
      history.appendChild(li);
    });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const name = (nameInput.value || '').trim();
    const email = (emailInput.value || '').trim();
    const message = (messageInput.value || '').trim();

    if (!name || !email || !message) {
      status.className = 'status error';
      status.textContent = 'Name, email, and message are required.';
      return;
    }
    if (!email.includes('@')) {
      status.className = 'status error';
      status.textContent = 'Enter a valid email address.';
      return;
    }

    const items = loadMessages();
    items.unshift({ name, email, message });
    saveMessages(items);
    render();
    status.className = 'status ok';
    status.textContent = `Message sent: ${name}`;
    form.reset();
  });

  resetBtn.addEventListener('click', function () {
    form.reset();
    status.className = 'status';
    status.textContent = 'Form cleared. Previous messages remain listed below.';
  });

  render();
})();
