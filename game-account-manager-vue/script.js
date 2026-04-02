const accounts = [
  {
    id: 1,
    game: "League of Legends",
    username: "summoner88",
    email: "summoner88@email.com",
    region: "OCE",
    level: 45,
    status: "Active",
    notes: "Main ranked account"
  },
  {
    id: 2,
    game: "Genshin Impact",
    username: "travelerSky",
    email: "traveler@email.com",
    region: "Asia",
    level: 60,
    status: "Active",
    notes: "Daily quests account"
  },
  {
    id: 3,
    game: "Valorant",
    username: "aceShot",
    email: "ace@email.com",
    region: "NA",
    level: 31,
    status: "Inactive",
    notes: "Alt account for practice"
  }
];

let editingId = null;

const accountTableBody = document.getElementById("accountTableBody");
const totalAccounts = document.getElementById("totalAccounts");
const totalGames = document.getElementById("totalGames");
const highestLevel = document.getElementById("highestLevel");
const searchInput = document.getElementById("searchInput");
const regionFilter = document.getElementById("regionFilter");
const formSection = document.getElementById("formSection");
const formTitle = document.getElementById("formTitle");

const fields = {
  gameName: document.getElementById("gameName"),
  username: document.getElementById("username"),
  email: document.getElementById("email"),
  region: document.getElementById("region"),
  level: document.getElementById("level"),
  status: document.getElementById("status"),
  notes: document.getElementById("notes")
};

function renderAccounts() {
  const keyword = searchInput.value.trim().toLowerCase();
  const selectedRegion = regionFilter.value;

  const filteredAccounts = accounts.filter((account) => {
    const matchesKeyword =
      account.game.toLowerCase().includes(keyword) ||
      account.username.toLowerCase().includes(keyword) ||
      account.email.toLowerCase().includes(keyword) ||
      account.region.toLowerCase().includes(keyword);

    const matchesRegion = selectedRegion === "all" || account.region === selectedRegion;

    return matchesKeyword && matchesRegion;
  });

  accountTableBody.innerHTML = "";

  filteredAccounts.forEach((account) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${account.game}</td>
      <td>${account.username}</td>
      <td>${account.email}</td>
      <td>${account.region}</td>
      <td>${account.level}</td>
      <td><span class="tag">${account.status}</span></td>
      <td>${account.notes || ""}</td>
      <td>
        <div class="actions">
          <button class="secondary-btn" onclick="editAccount(${account.id})">Edit</button>
          <button class="danger-btn" onclick="deleteAccount(${account.id})">Delete</button>
        </div>
      </td>
    `;
    accountTableBody.appendChild(row);
  });

  updateStats();
}

function updateStats() {
  totalAccounts.textContent = accounts.length;
  totalGames.textContent = new Set(accounts.map((account) => account.game)).size;
  highestLevel.textContent = Math.max(0, ...accounts.map((account) => Number(account.level) || 0));
}

function clearForm() {
  fields.gameName.value = "";
  fields.username.value = "";
  fields.email.value = "";
  fields.region.value = "OCE";
  fields.level.value = "";
  fields.status.value = "Active";
  fields.notes.value = "";
  editingId = null;
  formTitle.textContent = "Add New Account";
}

function showForm() {
  formSection.classList.remove("hidden");
}

function hideForm() {
  formSection.classList.add("hidden");
  clearForm();
}

function saveAccount() {
  const newAccount = {
    game: fields.gameName.value.trim(),
    username: fields.username.value.trim(),
    email: fields.email.value.trim(),
    region: fields.region.value,
    level: Number(fields.level.value),
    status: fields.status.value,
    notes: fields.notes.value.trim()
  };

  if (!newAccount.game || !newAccount.username || !newAccount.email || !newAccount.level) {
    alert("Please fill in Game Name, Username, Email, and Level.");
    return;
  }

  if (editingId !== null) {
    const index = accounts.findIndex((account) => account.id === editingId);
    accounts[index] = { ...accounts[index], ...newAccount };
  } else {
    accounts.push({ id: Date.now(), ...newAccount });
  }

  renderAccounts();
  hideForm();
}

window.editAccount = function (id) {
  const account = accounts.find((item) => item.id === id);
  if (!account) {
    return;
  }

  editingId = id;
  formTitle.textContent = "Edit Account";
  fields.gameName.value = account.game;
  fields.username.value = account.username;
  fields.email.value = account.email;
  fields.region.value = account.region;
  fields.level.value = account.level;
  fields.status.value = account.status;
  fields.notes.value = account.notes;
  showForm();
};

window.deleteAccount = function (id) {
  const confirmed = confirm("Are you sure you want to delete this account?");
  if (!confirmed) {
    return;
  }

  const index = accounts.findIndex((account) => account.id === id);
  if (index !== -1) {
    accounts.splice(index, 1);
    renderAccounts();
  }
};

document.getElementById("showFormBtn").addEventListener("click", () => {
  clearForm();
  showForm();
});

document.getElementById("cancelBtn").addEventListener("click", hideForm);
document.getElementById("saveBtn").addEventListener("click", saveAccount);
searchInput.addEventListener("input", renderAccounts);
regionFilter.addEventListener("change", renderAccounts);

renderAccounts();