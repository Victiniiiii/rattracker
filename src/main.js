let invoke, convertFileSrc, readTextFile, writeTextFile, exists, BaseDirectory, Command, platform;
const tauri = window.__TAURI__;
invoke = tauri.core.invoke;
convertFileSrc = tauri.core.convertFileSrc;
({ readTextFile, writeTextFile, exists, BaseDirectory } = tauri.fs);
Command = tauri.shell.Command;
platform = tauri.os.platform;

// TODO: Fix this weird imports

// TODO: One more TODO below

// TODO: Disallow tauri reading everywhere ("*" at config)

const CONFIG_FILE = "config.json";

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
};

async function loadConfig() {
	return { ...DEFAULTS }; // TODO: FIX READING THE CONFIG FILE!!!! MAYBE EVEN LOCALSTORAGE!!

	try {
		const fileExists = await exists(CONFIG_FILE, { dir: BaseDirectory.App });
		if (fileExists) {
			const text = await readTextFile(CONFIG_FILE, { dir: BaseDirectory.App });
			return { ...DEFAULTS, ...JSON.parse(text) };
		}
	} catch (e) {
		console.warn("Error reading config.json:", e);
	}
	return { ...DEFAULTS };
}

async function saveConfig(cfg) {
	await writeTextFile(CONFIG_FILE, JSON.stringify(cfg, null, 2), { dir: BaseDirectory.App });
}

function populateForm(cfg) {
	const form = document.getElementById("configForm");
	for (const [key, value] of Object.entries(cfg)) {
		const input = form.elements[key];
		if (!input) continue;
		if (input.type == "checkbox") input.checked = !!value;
		else input.value = value ?? "";
	}
}

function readForm() {
	const form = document.getElementById("configForm");
	const cfg = {};
	for (const el of form.elements) {
		if (!el.name) continue;
		if (el.type == "checkbox") cfg[el.name] = el.checked;
		else if (el.type == "number") cfg[el.name] = el.value == "" ? null : Number(el.value);
		else cfg[el.name] = el.value;
	}
	return cfg;
}

function buildArgs(selectedFile, cfg) {
	const args = ["--video", selectedFile];

	const startVal = document.getElementById("startTime").value;
	if (startVal != "") args.push("--start", startVal);

	const endVal = document.getElementById("endTime").value;
	if (endVal != "") args.push("--end", endVal);

	args.push("--pool_radius_cm", document.getElementById("poolRadius").value);
	args.push("--mog2_history", String(cfg.mog2_history));
	args.push("--mog2_threshold", String(cfg.mog2_threshold));
	if (cfg.mog2_detect_shadow) args.push("--mog2_detect_shadow");
	args.push("--morph_open_k", String(cfg.morph_open_k));
	args.push("--morph_close_k", String(cfg.morph_close_k));
	args.push("--min_contour_area", String(cfg.min_contour_area));
	args.push("--max_contour_area", String(cfg.max_contour_area));
	args.push("--trail_len", String(cfg.trail_len));
	args.push("--debug_frames", String(cfg.debug_frames));

	if (cfg.pool_west) args.push("--pool_west", cfg.pool_west);
	if (cfg.pool_north) args.push("--pool_north", cfg.pool_north);
	if (cfg.pool_east) args.push("--pool_east", cfg.pool_east);
	if (cfg.pool_south) args.push("--pool_south", cfg.pool_south);

	return args;
}

function showPhase(phase) {
	document.getElementById("beforeScript").hidden = phase != "before";
	document.getElementById("duringScript").hidden = phase != "during";
	document.getElementById("afterScript").hidden = phase != "after";
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

document.addEventListener("DOMContentLoaded", async () => {
	let selectedFile = null;
	let pythonProcess = null;
	let cfg = await loadConfig();

	populateForm(cfg);
	showPhase("before");

	document.getElementById("settings").onclick = () => {
		document.getElementById("settingsPanel").hidden = false;
	};

	document.getElementById("closeSettings").onclick = () => {
		document.getElementById("settingsPanel").hidden = true;
		populateForm(cfg);
	};

	document.getElementById("configForm").onsubmit = async e => {
		e.preventDefault();
		cfg = readForm();
		await saveConfig(cfg);
		document.getElementById("settingsPanel").hidden = true;
	};

	document.getElementById("selectFile").onclick = async () => {
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

	for (const tab of document.querySelectorAll(".tab")) {
		tab.onclick = () => {
			document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
			document.querySelectorAll(".tabContent").forEach(t => {
				t.hidden = true;
			});
			tab.classList.add("active");
			document.getElementById("tab" + tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1)).hidden = false;
		};
	}

	document.getElementById("runAgainBtn").onclick = () => {
		showPhase("before");
		document.getElementById("outputVideo").src = "";
		document.getElementById("csvTable").innerHTML = "";
		document.getElementById("summaryText").textContent = "";
	};

	document.getElementById("runBtn").onclick = async () => {
		if (!selectedFile) return;

		document.getElementById("progressBar").value = 0;
		document.getElementById("progressText").textContent = "0%";
		document.getElementById("etaText").textContent = "";
		document.getElementById("frameText").textContent = "";

		const args = buildArgs(selectedFile, cfg);

		pythonProcess = Command.sidecar("bin/main", args);

		let duringStarted = false;

		pythonProcess.stdout.on("data", async line => {
			let parsed;
			try {
				parsed = JSON.parse(line);
			} catch {
				return;
			}

			if (parsed.progress != undefined) {
				if (!duringStarted) {
					duringStarted = true;
					showPhase("during");
				}
				const pct = parsed.progress;
				document.getElementById("progressBar").value = pct;
				document.getElementById("progressText").textContent = `${pct.toFixed(1)}%`;
				document.getElementById("frameText").textContent = `Frame ${parsed.frame} / ${parsed.total}`;
				document.getElementById("etaText").textContent = parsed.eta > 0 ? `ETA: ${parsed.eta}s` : "";
			}

			if (parsed.done) {
				cfg = { ...cfg };
				await saveConfig(cfg);

				try {
					document.getElementById("outputVideo").src = convertFileSrc(parsed.video_out);
				} catch {}

				try {
					const csvText = await readTextFile(parsed.csv_out);
					renderCsvTable(csvText);
				} catch {}

				try {
					const summaryText = await readTextFile(parsed.summary_out);
					document.getElementById("summaryText").textContent = summaryText;
				} catch {}

				showPhase("after");
			}
		});

		pythonProcess.stderr.on("data", line => {
			console.error("stderr:", line);
		});

		pythonProcess.on("close", code => {
			console.log("Process exited:", code);
			pythonProcess = null;
		});

		await pythonProcess.spawn();
	};

	document.getElementById("cancelBtn").onclick = () => {
		if (pythonProcess) {
			pythonProcess.kill();
			pythonProcess = null;
		}
		showPhase("before");
		document.getElementById("progressBar").value = 0;
		document.getElementById("progressText").textContent = "0%";
		document.getElementById("etaText").textContent = "";
		document.getElementById("frameText").textContent = "";
	};
});
