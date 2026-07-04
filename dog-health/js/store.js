// localStorage 기반 데이터 저장소

const STORE_KEY = "dogHealth.v1";

function loadDB() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return { dogs: [], records: [], activeDogId: null };
    const db = JSON.parse(raw);
    db.dogs = db.dogs || [];
    db.records = db.records || [];
    return db;
  } catch (e) {
    console.error("데이터 불러오기 실패", e);
    return { dogs: [], records: [], activeDogId: null };
  }
}

function saveDB(db) {
  localStorage.setItem(STORE_KEY, JSON.stringify(db));
}

function uid() {
  return (
    Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
  );
}

const Store = {
  db: loadDB(),

  persist() {
    saveDB(this.db);
  },

  getDogs() {
    return this.db.dogs;
  },

  getDog(id) {
    return this.db.dogs.find((d) => d.id === id);
  },

  getActiveDog() {
    return this.getDog(this.db.activeDogId) || this.db.dogs[0] || null;
  },

  setActiveDog(id) {
    this.db.activeDogId = id;
    this.persist();
  },

  addDog(dog) {
    const d = { id: uid(), ...dog };
    this.db.dogs.push(d);
    this.db.activeDogId = d.id;
    this.persist();
    return d;
  },

  updateDog(id, patch) {
    const d = this.getDog(id);
    if (d) Object.assign(d, patch);
    this.persist();
  },

  deleteDog(id) {
    this.db.dogs = this.db.dogs.filter((d) => d.id !== id);
    this.db.records = this.db.records.filter((r) => r.dogId !== id);
    if (this.db.activeDogId === id) {
      this.db.activeDogId = this.db.dogs[0] ? this.db.dogs[0].id : null;
    }
    this.persist();
  },

  // 특정 개의 기록을 날짜 오름차순으로 반환
  getRecords(dogId) {
    return this.db.records
      .filter((r) => r.dogId === dogId)
      .sort((a, b) => a.date.localeCompare(b.date));
  },

  addRecord(rec) {
    const r = { id: uid(), ...rec };
    this.db.records.push(r);
    this.persist();
    return r;
  },

  updateRecord(id, patch) {
    const r = this.db.records.find((x) => x.id === id);
    if (r) Object.assign(r, patch);
    this.persist();
  },

  deleteRecord(id) {
    this.db.records = this.db.records.filter((r) => r.id !== id);
    this.persist();
  },

  exportJSON() {
    return JSON.stringify(this.db, null, 2);
  },

  importJSON(text) {
    const parsed = JSON.parse(text);
    if (!parsed.dogs || !parsed.records) throw new Error("형식이 올바르지 않습니다.");
    this.db = parsed;
    this.persist();
  },
};
