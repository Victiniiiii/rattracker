let invoke, convertFileSrc, readTextFile, writeTextFile, Command;
const tauri = window.__TAURI__;
invoke = tauri.core.invoke;
convertFileSrc = tauri.core.convertFileSrc;
({ readTextFile, writeTextFile } = tauri.fs);
Command = tauri.shell.Command;

const STORAGE_KEY = "rattracker_config";

const DEFAULTS = {
	mog2_history: 120,
	mog2_threshold: 40,
	mog2_detect_shadow: false,
	morph_open_k: 3,
	morph_close_k: 15,
	min_contour_area: 300,
	max_contour_area: 12000,
	trail_len: 40,
	debug_frames: 0,
	pool_west: "",
	pool_north: "",
	pool_east: "",
	pool_south: "",
	language: "en",
};

const I18N = {
	en: {
		title: "Rat Tracker",
		settings: "Settings",
		detection: "Detection",
		mog2_history: "MOG2 History",
		mog2_threshold: "MOG2 Threshold",
		detect_shadows: "Detect Shadows",
		morph_open: "Morph Open Kernel",
		morph_close: "Morph Close Kernel",
		min_area: "Min Contour Area (px²)",
		max_area: "Max Contour Area (px²)",
		trail_len: "Trail Length (frames)",
		debug_frames: "Debug Frames",
		pool_calib: "Pool Calibration Cache",
		pool_note: "Auto-filled after first calibration. Edit to reuse across runs.",
		pool_west: "Pool West (x,y)",
		pool_north: "Pool North (x,y)",
		pool_east: "Pool East (x,y)",
		pool_south: "Pool South (x,y)",
		save: "Save",
		cancel: "Cancel",
		select_video: "Select Video",
		no_file: "No video selected",
		start_time: "Start (s)",
		end_time: "End (s)",
		pool_radius: "Radius (cm)",
		run: "Run",
		tab_video: "Video",
		tab_csv: "CSV",
		tab_summary: "Summary",
	},
	fr: {
		title: "Rat Tracker",
		settings: "Paramètres",
		detection: "Détection",
		mog2_history: "Historique MOG2",
		mog2_threshold: "Seuil MOG2",
		detect_shadows: "Détecter les ombres",
		morph_open: "Noyau ouverture morph.",
		morph_close: "Noyau fermeture morph.",
		min_area: "Surface contour min. (px²)",
		max_area: "Surface contour max. (px²)",
		trail_len: "Longueur trace (images)",
		debug_frames: "Images de débogage",
		pool_calib: "Cache calibration bassin",
		pool_note: "Rempli automatiquement après la première calibration.",
		pool_west: "Bassin Ouest (x,y)",
		pool_north: "Bassin Nord (x,y)",
		pool_east: "Bassin Est (x,y)",
		pool_south: "Bassin Sud (x,y)",
		save: "Enregistrer",
		cancel: "Annuler",
		select_video: "Choisir une vidéo",
		no_file: "Aucun video sélectionné",
		start_time: "Début (s)",
		end_time: "Fin (s)",
		pool_radius: "Rayon (cm)",
		run: "Lancer",
		tab_video: "Vidéo",
		tab_csv: "CSV",
		tab_summary: "Résumé",
	},
	tr: {
		title: "Fare İzleyici",
		settings: "Ayarlar",
		detection: "Algılama",
		mog2_history: "MOG2 Geçmişi",
		mog2_threshold: "MOG2 Eşiği",
		detect_shadows: "Gölgeleri Algıla",
		morph_open: "Morfoloji Açma Çekirdeği",
		morph_close: "Morfoloji Kapama Çekirdeği",
		min_area: "Min Kontur Alanı (px²)",
		max_area: "Maks Kontur Alanı (px²)",
		trail_len: "İz Uzunluğu (kare)",
		debug_frames: "Hata Ayıklama Kareleri",
		pool_calib: "Havuz Kalibrasyon Önbelleği",
		pool_note: "İlk kalibrasyondan sonra otomatik doldurulur.",
		pool_west: "Havuzun Batısı (x,y)",
		pool_north: "Havuzun Kuzeyi (x,y)",
		pool_east: "Havuzun Doğusu (x,y)",
		pool_south: "Havuzun Güneyi (x,y)",
		save: "Kaydet",
		cancel: "İptal",
		select_video: "Video Seç",
		no_file: "Video seçilmedi",
		start_time: "Başlangıç (s)",
		end_time: "Bitiş (s)",
		pool_radius: "Yarıçap (cm)",
		run: "Çalıştır",
		tab_video: "Video",
		tab_csv: "CSV",
		tab_summary: "Özet",
	},
};

const LANG_META = {
	en: { flag: "assets/uk.svg", name: "English" },
	fr: { flag: "assets/fr.svg", name: "Français" },
	tr: { flag: "assets/tr.svg", name: "Türkçe" },
};

let selectedFile = null;
let pythonProcess = null;
let cfg = { ...DEFAULTS };

function loadConfig() {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
	} catch (e) {
		console.warn("Error reading localStorage:", e);
	}
	return { ...DEFAULTS };
}

function saveConfig(c) {
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(c));
	} catch (e) {
		console.warn("Error saving to localStorage:", e);
	}
}

function t(key) {
	return I18N[cfg.language]?.[key] ?? I18N.en[key] ?? key;
}

function applyI18n() {
	document.querySelectorAll("[data-i18n]").forEach(el => {
		const key = el.getAttribute("data-i18n");
		const input = el.querySelector("input");
		if (input) {
			el.childNodes[0].textContent = t(key);
		} else {
			el.textContent = t(key);
		}
	});

	const noFile = document.getElementById("filePath");
	if (!selectedFile) noFile.textContent = t("no_file");

	const meta = LANG_META[cfg.language];
	document.getElementById("langFlagSelected").src = meta.flag;
	document.getElementById("langNameSelected").textContent = meta.name;
}

window.toggleLangDropdown = function () {
	const menu = document.getElementById("langMenu");
	menu.hidden = !menu.hidden;
};

window.selectLang = function (lang) {
	cfg.language = lang;
	saveConfig(cfg);
	applyI18n();
	document.getElementById("langMenu").hidden = true;
};

document.addEventListener("click", e => {
	const dropdown = document.getElementById("langDropdown");
	if (!dropdown.contains(e.target)) {
		document.getElementById("langMenu").hidden = true;
	}
});

function populateForm(c) {
	const form = document.getElementById("configForm");
	for (const [key, value] of Object.entries(c)) {
		const input = form.elements[key];
		if (!input) continue;
		if (input.type === "checkbox") input.checked = !!value;
		else input.value = value ?? "";
	}
}

function readForm() {
	const form = document.getElementById("configForm");
	const c = {};
	for (const el of form.elements) {
		if (!el.name) continue;
		if (el.type === "checkbox") c[el.name] = el.checked;
		else if (el.type === "number") c[el.name] = el.value === "" ? null : Number(el.value);
		else c[el.name] = el.value;
	}
	return c;
}

function buildArgs(filePath, c) {
	const args = ["--video", filePath, "--language", cfg.language];

	const startVal = document.getElementById("startTime").value;
	if (startVal !== "") args.push("--start", startVal);

	const endVal = document.getElementById("endTime").value;
	if (endVal !== "") args.push("--end", endVal);

	args.push("--pool_radius_cm", document.getElementById("poolRadius").value);
	args.push("--mog2_history", String(c.mog2_history));
	args.push("--mog2_threshold", String(c.mog2_threshold));
	if (c.mog2_detect_shadow) args.push("--mog2_detect_shadow");
	args.push("--morph_open_k", String(c.morph_open_k));
	args.push("--morph_close_k", String(c.morph_close_k));
	args.push("--min_contour_area", String(c.min_contour_area));
	args.push("--max_contour_area", String(c.max_contour_area));
	args.push("--trail_len", String(c.trail_len));
	args.push("--debug_frames", String(c.debug_frames));

	if (c.pool_west) args.push("--pool_west", c.pool_west);
	if (c.pool_north) args.push("--pool_north", c.pool_north);
	if (c.pool_east) args.push("--pool_east", c.pool_east);
	if (c.pool_south) args.push("--pool_south", c.pool_south);

	args.push("--appmode");
	return args;
}

function setUIRunning(running) {
	document.getElementById("selectFileBtn").disabled = running;
	document.getElementById("runBtn").disabled = running || !selectedFile;
	document.getElementById("cancelBtn").disabled = !running;
	document.getElementById("settingsBtn").disabled = running;
	document.getElementById("langBtn").disabled = running;

	document.getElementById("startTime").disabled = running;
	document.getElementById("endTime").disabled = running;
	document.getElementById("poolRadius").disabled = running;
}

function renderCsvTable(csvText) {
	const lines = csvText.trim().split("\n");
	if (!lines.length) return;
	const headers = lines[0].split(",");
	let html = "<table><thead><tr>";
	for (const h of headers) html += `<th>${h}</th>`;
	html += "</tr></thead><tbody>";
	for (let i = 1; i < lines.length; i++) {
		const cols = lines[i].split(",");
		html += "<tr>";
		for (const c of cols) html += `<td>${c}</td>`;
		html += "</tr>";
	}
	html += "</tbody></table>";
	document.getElementById("csvTable").innerHTML = html;
}

window.openSettings = function () {
	document.getElementById("settingsOverlay").hidden = false;
};

window.closeSettings = function () {
	document.getElementById("settingsOverlay").hidden = true;
	populateForm(cfg);
};

window.overlayClose = function (e) {
	if (e.target === document.getElementById("settingsOverlay")) closeSettings();
};

window.saveSettings = async function (e) {
	e.preventDefault();
	const formData = readForm();
	cfg = { ...cfg, ...formData };
	saveConfig(cfg);
	document.getElementById("settingsOverlay").hidden = true;
};

window.selectFile = async function () {
	try {
		selectedFile = await invoke("pick_file");
		if (selectedFile) {
			document.getElementById("filePath").textContent = selectedFile;
			document.getElementById("runBtn").disabled = false;
		}
	} catch (e) {
		console.log("No file selected:", e);
	}
};

window.switchTab = function (tab) {
	document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
	document.querySelectorAll(".tabContent").forEach(t => {
		t.hidden = true;
	});
	tab.classList.add("active");
	const id = "tab" + tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1);
	document.getElementById(id).hidden = false;
};

window.runScript = async function () {
	if (!selectedFile) return;

	document.getElementById("progressBar").value = 0;
	document.getElementById("progressText").textContent = "0%";
	document.getElementById("etaText").textContent = "";

	setUIRunning(true);

	const args = buildArgs(selectedFile, cfg);
	pythonProcess = Command.sidecar("bin/main", args);

	pythonProcess.stdout.on("data", async line => {
		let parsed;
		try {
			parsed = JSON.parse(line);
		} catch {
			return;
		}

		if (parsed.progress != undefined) {
			const pct = parsed.progress;
			document.getElementById("progressBar").value = pct;
			document.getElementById("progressText").textContent = `${pct.toFixed(1)}%`;
			document.getElementById("etaText").textContent = parsed.eta > 0 ? `ETA: ${parsed.eta}s` : "";
		}

		if (parsed.done) {
			saveConfig(cfg);

			try {
				const fileBytes = await tauri.fs.readFile(parsed.video_out);
				const blob = new Blob([fileBytes], { type: "video/mp4" });
				const blobUrl = URL.createObjectURL(blob);
				const videoEl = document.getElementById("outputVideo");
				videoEl.src = blobUrl;
				videoEl.load();
			} catch (e) {
				console.error("Video load error:", e);
			}

			try {
				const csvText = await readTextFile(parsed.csv_out);
				renderCsvTable(csvText);
			} catch (e) {
				console.error("CSV load error:", e);
			}

			try {
				const summaryText = await readTextFile(parsed.summary_out);
				document.getElementById("summaryText").textContent = summaryText;
			} catch (e) {
				console.error("Summary load error:", e);
			}

			setUIRunning(false);
		}
	});

	pythonProcess.stderr.on("data", line => {
		console.error("stderr:", line);
	});

	pythonProcess.on("close", code => {
		console.log("Process exited:", code);
		pythonProcess = null;
		setUIRunning(false);
	});

	await pythonProcess.spawn();
};

window.cancelScript = function () {
	if (pythonProcess) {
		pythonProcess.kill();
		pythonProcess = null;
	}
	setUIRunning(false);
	document.getElementById("progressBar").value = 0;
	document.getElementById("progressText").textContent = "—";
	document.getElementById("etaText").textContent = "";
};

document.addEventListener("DOMContentLoaded", () => {
	cfg = loadConfig();
	populateForm(cfg);
	applyI18n();
	setUIRunning(false);
});
