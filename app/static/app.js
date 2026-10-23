/* 无依赖原生 JS。所有请求统一走 api()，便于加 token。 */
(function () {
  'use strict';

  var TOKEN = new URLSearchParams(location.search).get('token') || localStorage.getItem('appToken') || '';
  if (TOKEN) localStorage.setItem('appToken', TOKEN);

  function api(path, opts) {
    opts = opts || {};
    if (TOKEN) {
      opts.headers = Object.assign({}, opts.headers, { 'X-Token': TOKEN });
    }
    return fetch(path, opts).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok || j.ok === false) throw new Error(j.error || ('HTTP ' + r.status));
        return j;
      });
    });
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function fmtSize(b) {
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    return (b / 1048576).toFixed(2) + ' MB';
  }

  function fmtTime(ts) {
    var d = new Date(ts * 1000);
    var p = function (n) { return n < 10 ? '0' + n : '' + n; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /* ---------------- tabs ---------------- */
  var tabs = document.querySelectorAll('.tab');
  Array.prototype.forEach.call(tabs, function (t) {
    t.addEventListener('click', function () {
      Array.prototype.forEach.call(tabs, function (x) { x.classList.remove('active'); });
      Array.prototype.forEach.call(document.querySelectorAll('.panel'), function (p) { p.classList.remove('active'); });
      t.classList.add('active');
      document.getElementById('panel-' + t.dataset.tab).classList.add('active');
    });
  });

  /* ---------------- health ---------------- */
  function checkHealth() {
    var dot = document.getElementById('statusDot');
    api('/api/health').then(function (j) {
      dot.className = 'dot ok';
      document.getElementById('backendTag').textContent = j.data.backend;
    }).catch(function () {
      dot.className = 'dot bad';
      document.getElementById('backendTag').textContent = 'offline';
    });
  }

  /* ---------------- notes ---------------- */
  var notesHint = document.getElementById('notesHint');
  var notesList = document.getElementById('notesList');

  function loadNotes() {
    notesList.innerHTML = '';
    api('/api/notes').then(function (j) {
      var notes = j.data || [];
      notesHint.textContent = notes.length ? notes.length + ' 条笔记' : '还没有笔记，写一条试试';
      notes.forEach(renderNote);
    }).catch(function (e) { notesHint.textContent = '加载失败：' + e.message; });
  }

  function renderNote(n) {
    var li = el('li', 'item');
    var head = el('div', 'item-head');
    var title = el('div', 'item-title', n.title);
    var actions = el('div', 'actions');

    var editBtn = el('button', 'btn mini', '编辑');
    var delBtn = el('button', 'btn mini danger', '删除');

    editBtn.addEventListener('click', function () {
      // 就地编辑：换成输入框，保存走 PUT
      var wrap = el('div');
      var ti = el('input', 'input');
      ti.value = n.title;
      var bo = el('textarea', 'textarea');
      bo.rows = 4;
      bo.value = n.body;
      var save = el('button', 'btn primary mini', '保存');
      var cancel = el('button', 'btn mini', '取消');
      var bar = el('div', 'row');
      bar.style.marginTop = '8px';
      bar.appendChild(save);
      bar.appendChild(cancel);
      wrap.appendChild(ti);
      wrap.appendChild(bo);
      wrap.appendChild(bar);
      li.innerHTML = '';
      li.appendChild(wrap);

      cancel.addEventListener('click', function () { li.remove(); renderNote(n); });
      save.addEventListener('click', function () {
        api('/api/notes/' + n.id, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: ti.value.trim() || n.title, body: bo.value })
        }).then(loadNotes).catch(function (e) { alert('保存失败：' + e.message); });
      });
    });

    delBtn.addEventListener('click', function () {
      if (!confirm('删除「' + n.title + '」？')) return;
      api('/api/notes/' + n.id, { method: 'DELETE' }).then(loadNotes)
        .catch(function (e) { alert('删除失败：' + e.message); });
    });

    actions.appendChild(editBtn);
    actions.appendChild(delBtn);
    head.appendChild(title);
    head.appendChild(actions);
    li.appendChild(head);
    if (n.body) li.appendChild(el('div', 'item-body', n.body));
    li.appendChild(el('div', 'item-meta', fmtTime(n.updated_at)));
    notesList.appendChild(li);
  }

  document.getElementById('addNote').addEventListener('click', function () {
    var ti = document.getElementById('noteTitle');
    var bo = document.getElementById('noteBody');
    var title = ti.value.trim();
    if (!title) { ti.focus(); return; }
    api('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title, body: bo.value })
    }).then(function () { ti.value = ''; bo.value = ''; loadNotes(); })
      .catch(function (e) { alert('新建失败：' + e.message); });
  });

  /* ---------------- uploads ---------------- */
  var upHint = document.getElementById('uploadHint');
  var upList = document.getElementById('uploadsList');

  function loadUploads() {
    upList.innerHTML = '';
    api('/api/uploads').then(function (j) {
      var files = j.data || [];
      upHint.textContent = files.length ? files.length + ' 个文件' : '还没有文件';
      files.forEach(function (f) {
        var li = el('li', 'item');
        var head = el('div', 'item-head');
        head.appendChild(el('div', 'item-title', f.name));
        var actions = el('div', 'actions');

        var a = el('a', 'btn mini', '下载');
        a.href = '/api/uploads/' + encodeURIComponent(f.name) + '/download' + (TOKEN ? '?token=' + encodeURIComponent(TOKEN) : '');
        actions.appendChild(a);

        var del = el('button', 'btn mini danger', '删除');
        del.addEventListener('click', function () {
          if (!confirm('删除 ' + f.name + '？')) return;
          api('/api/uploads/' + encodeURIComponent(f.name), { method: 'DELETE' })
            .then(loadUploads).catch(function (e) { alert('删除失败：' + e.message); });
        });
        actions.appendChild(del);

        head.appendChild(actions);
        li.appendChild(head);
        li.appendChild(el('div', 'item-meta', fmtSize(f.size) + ' · ' + fmtTime(f.mtime)));
        upList.appendChild(li);
      });
    }).catch(function (e) { upHint.textContent = '加载失败：' + e.message; });
  }

  function uploadFiles(fileList) {
    if (!fileList || !fileList.length) return;
    var fd = new FormData();
    Array.prototype.forEach.call(fileList, function (f) { fd.append('files', f, f.name); });
    upHint.textContent = '上传中…';
    api('/api/uploads', { method: 'POST', body: fd })
      .then(function () { loadUploads(); })
      .catch(function (e) { upHint.textContent = '上传失败：' + e.message; });
  }

  var input = document.getElementById('fileInput');
  var dz = document.getElementById('dropzone');
  dz.addEventListener('click', function () { input.click(); });
  input.addEventListener('change', function () { uploadFiles(input.files); input.value = ''; });
  ['dragenter', 'dragover'].forEach(function (ev) {
    dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('over'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('over'); });
  });
  dz.addEventListener('drop', function (e) { uploadFiles(e.dataTransfer.files); });

  /* ---------------- system ---------------- */
  function loadSys() {
    var out = document.getElementById('sysOut');
    api('/api/sysinfo').then(function (j) {
      out.textContent = JSON.stringify(j.data, null, 2);
    }).catch(function (e) { out.textContent = '加载失败：' + e.message; });
  }
  document.getElementById('refreshSys').addEventListener('click', loadSys);

  /* ---------------- boot ---------------- */
  checkHealth();
  loadNotes();
  loadUploads();
  loadSys();
  setInterval(checkHealth, 30000);
})();
