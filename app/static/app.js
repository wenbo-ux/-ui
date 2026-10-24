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

  /* ---------------- image generation ---------------- */
  var pvList = document.getElementById('pvList');
  var imgProvider = document.getElementById('imgProvider');
  var imgHint = document.getElementById('imgHint');
  var gallery = document.getElementById('imgGallery');

  function loadKinds() {
    api('/api/providers/kinds').then(function (j) {
      var sel = document.getElementById('pvKind');
      sel.innerHTML = '';
      j.data.forEach(function (k) {
        var o = el('option');
        o.value = k.kind;
        o.textContent = k.desc;
        sel.appendChild(o);
      });
    }).catch(function () {});
  }

  function loadProviders() {
    api('/api/providers').then(function (j) {
      var list = j.data || [];
      pvList.innerHTML = '';
      imgProvider.innerHTML = '';

      if (!list.length) {
        pvList.appendChild(el('li', 'hint', '还没有配置，填好上面的表单保存'));
        var none = el('option');
        none.value = '';
        none.textContent = '（未配置 provider）';
        imgProvider.appendChild(none);
        return;
      }

      list.forEach(function (p) {
        var li = el('li', 'item');
        var head = el('div', 'item-head');
        head.appendChild(el('div', 'item-title', p.name));
        var acts = el('div', 'actions');
        var del = el('button', 'btn mini danger', '删除');
        del.addEventListener('click', function () {
          if (!confirm('删除配置「' + p.name + '」？')) return;
          api('/api/providers/' + p.id, { method: 'DELETE' })
            .then(loadProviders).catch(function (e) { alert(e.message); });
        });
        acts.appendChild(del);
        head.appendChild(acts);
        li.appendChild(head);
        li.appendChild(el('div', 'item-meta', p.kind + ' · ' + (p.model || '默认模型') + ' · ' + p.api_key));
        pvList.appendChild(li);

        var o = el('option');
        o.value = p.id;
        o.textContent = p.name + ' (' + (p.model || p.kind) + ')';
        imgProvider.appendChild(o);
      });

      var cur = localStorage.getItem('lastProvider');
      if (cur) imgProvider.value = cur;
      imgHint.textContent = '就绪，输入描述后点生成';
    }).catch(function (e) { imgHint.textContent = '加载配置失败：' + e.message; });
  }

  document.getElementById('pvSave').addEventListener('click', function () {
    var body = {
      kind: document.getElementById('pvKind').value,
      name: document.getElementById('pvName').value.trim(),
      base_url: document.getElementById('pvBase').value.trim(),
      api_key: document.getElementById('pvKey').value.trim(),
      model: document.getElementById('pvModel').value.trim()
    };
    if (!body.api_key) { alert('API Key 必填'); return; }
    api('/api/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function () {
      document.getElementById('pvKey').value = '';
      document.getElementById('pvName').value = '';
      loadProviders();
    }).catch(function (e) { alert('保存失败：' + e.message); });
  });

  imgProvider.addEventListener('change', function () {
    localStorage.setItem('lastProvider', imgProvider.value);
  });

  function loadImages() {
    api('/api/images').then(function (j) {
      var list = j.data || [];
      gallery.innerHTML = '';
      list.forEach(function (im) {
        var card = el('div', 'card');
        if (im.filename) {
          var img = el('img');
          img.src = '/api/images/file/' + encodeURIComponent(im.filename) + (TOKEN ? '?token=' + encodeURIComponent(TOKEN) : '');
          img.loading = 'lazy';
          img.addEventListener('click', function () { showLightbox(img.src); });
          card.appendChild(img);
        } else {
          var errBox = el('div', 'meta');
          errBox.textContent = '❌ ' + (im.error || '失败');
          errBox.style.color = '#ff8f8f';
          card.appendChild(errBox);
        }
        var meta = el('div', 'meta', im.prompt.slice(0, 60) + (im.prompt.length > 60 ? '…' : ''));
        card.appendChild(meta);
        var del = el('button', 'del', '×');
        del.addEventListener('click', function () {
          if (!confirm('删除这张图？')) return;
          api('/api/images/' + im.id, { method: 'DELETE' })
            .then(loadImages).catch(function (e) { alert(e.message); });
        });
        card.appendChild(del);
        gallery.appendChild(card);
      });
    }).catch(function () {});
  }

  function showLightbox(src) {
    var lb = document.getElementById('lightbox');
    document.getElementById('lightboxImg').src = src;
    lb.classList.add('show');
  }
  document.getElementById('lightbox').addEventListener('click', function () {
    this.classList.remove('show');
  });

  document.getElementById('imgGo').addEventListener('click', function () {
    var prompt = document.getElementById('imgPrompt').value.trim();
    var pid = imgProvider.value;
    if (!pid) { alert('请先在「API 配置」里添加一个 provider'); return; }
    if (!prompt) { document.getElementById('imgPrompt').focus(); return; }

    var btn = this;
    btn.disabled = true;
    imgHint.innerHTML = '<span class="spin"></span>生成中…可能需要几十秒';
    api('/api/images', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_id: Number(pid),
        prompt: prompt,
        size: document.getElementById('imgSize').value,
        n: 1
      })
    }).then(function () {
      imgHint.textContent = '生成完成';
      loadImages();
    }).catch(function (e) {
      imgHint.textContent = '失败：' + e.message;
      loadImages();
    }).then(function () { btn.disabled = false; });
  });

  /* ---------------- boot ---------------- */
  checkHealth();
  loadNotes();
  loadUploads();
  loadSys();
  loadKinds();
  loadProviders();
  loadImages();
  setInterval(checkHealth, 30000);
})();
