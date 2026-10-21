# =============================================================================
# Omnigensi // Makefile
# -----------------------------------------------------------------------------
# Semua perintah operasional project ada di sini.
# Jalankan `make` atau `make help` untuk melihat daftar perintah.
# =============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# -----------------------------------------------------------------------------
# Konfigurasi
# -----------------------------------------------------------------------------
COMPOSE        ?= docker compose
COMPOSE_FILE   ?= docker-compose.yml
COMPOSE_PROD   ?= docker compose -f docker-compose.yml -f docker-compose.prod.yml

BACKEND_SVC    := backend
FRONTEND_SVC   := frontend
DB_SVC         := postgres
REDIS_SVC      := redis

BACKEND_PORT   ?= 8123
FRONTEND_PORT  ?= 5296
POSTGRES_PORT  ?= 5558
REDIS_PORT     ?= 6505

ENV_FILE       ?= .env
PYTHON         := python3

# Warna output (fallback ke tanpa warna bila tidak didukung)
C_RESET  := $(shell tput -Txterm sgr0 2>/dev/null)
C_BOLD   := $(shell tput -Txterm bold 2>/dev/null)
C_CYAN   := $(shell tput -Txterm setaf 6 2>/dev/null)
C_GREEN  := $(shell tput -Txterm setaf 2 2>/dev/null)
C_YELLOW := $(shell tput -Txterm setaf 3 2>/dev/null)

.DEFAULT: help

# =============================================================================
# HELP
# =============================================================================
.PHONY: help
help: ## Tampilkan daftar perintah yang tersedia
	@echo ""
	@echo "  $(C_BOLD)Omnigensi // Command Reference$(C_RESET)"
	@echo "  ─────────────────────────────────────────────────────────────"
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(C_CYAN)%-22s$(C_RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "  $(C_BOLD)Port default$(C_RESET): frontend $(FRONTEND_PORT) · backend $(BACKEND_PORT) · postgres $(POSTGRES_PORT) · redis $(REDIS_PORT)"
	@echo ""

# =============================================================================
# SETUP & ENVIRONMENT
# =============================================================================
.PHONY: init
init: env ## Setup awal: buat .env dari contoh (aman untuk dijalankan berulang)
	@echo "$(C_GREEN)✔$(C_RESET) Setup selesai. Lanjutkan dengan: make up"

.PHONY: env
env: ## Buat file .env dari .env.example bila belum ada
	@if [ -f $(ENV_FILE) ]; then \
		echo "$(C_YELLOW)•$(C_RESET) $(ENV_FILE) sudah ada, tidak ditimpa."; \
	else \
		cp .env.example $(ENV_FILE); \
		echo "$(C_GREEN)✔$(C_RESET) $(ENV_FILE) dibuat dari .env.example"; \
	fi

.PHONY: env-check
env-check: ## Verifikasi .env dan variabel wajib terisi
	@test -f $(ENV_FILE) || { echo "$(C_YELLOW)✖$(C_RESET) $(ENV_FILE) belum ada. Jalankan: make env"; exit 1; }
	@grep -q '^ENCRYPTION_KEY=.\+' $(ENV_FILE) \
		&& echo "$(C_GREEN)✔$(C_RESET) ENCRYPTION_KEY terisi" \
		|| { echo "$(C_YELLOW)✖$(C_RESET) ENCRYPTION_KEY kosong di $(ENV_FILE)"; exit 1; }

.PHONY: doctor
doctor: ## Cek prasyarat: docker, compose, make, port bebas
	@echo "Memeriksa prasyarat..."
	@command -v docker >/dev/null || { echo "$(C_YELLOW)✖$(C_RESET) docker tidak ditemukan"; exit 1; }
	@echo "$(C_GREEN)✔$(C_RESET) docker: $$(docker --version)"
	@docker compose version >/dev/null 2>&1 || { echo "$(C_YELLOW)✖$(C_RESET) docker compose plugin tidak tersedia"; exit 1; }
	@echo "$(C_GREEN)✔$(C_RESET) compose: $$(docker compose version --short 2>/dev/null)"
	@echo "$(C_GREEN)✔$(C_RESET) make: $$(make --version | head -1)"
	@for p in $(FRONTEND_PORT) $(BACKEND_PORT) $(POSTGRES_PORT) $(REDIS_PORT); do \
		if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -qE ":$$p "; then \
			echo "$(C_YELLOW)•$(C_RESET) port $$p sedang dipakai"; \
		else \
			echo "$(C_GREEN)✔$(C_RESET) port $$p bebas"; \
		fi; \
	done

# =============================================================================
# LIFECYCLE (DEVELOPMENT)
# =============================================================================
.PHONY: up
up: env ## Nyalakan seluruh stack (build bila perlu) di background
	$(COMPOSE) up -d --build
	@echo "$(C_GREEN)✔$(C_RESET) Stack berjalan. Frontend: http://localhost:$(FRONTEND_PORT) · API docs: http://localhost:$(BACKEND_PORT)/docs"

.PHONY: upd
upd: ## Nyalakan stack tanpa rebuild image
	$(COMPOSE) up -d

.PHONY: down
down: ## Matikan seluruh stack (data volume dipertahankan)
	$(COMPOSE) down
	@echo "$(C_GREEN)✔$(C_RESET) Stack dihentikan."

.PHONY: restart
restart: ## Restart seluruh stack
	$(COMPOSE) restart

.PHONY: rebuild
rebuild: ## Rebuild image dari nol lalu nyalakan ulang
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d
	@echo "$(C_GREEN)✔$(C_RESET) Rebuild selesai."

.PHONY: stop
stop: ## Stop container tanpa menghapusnya
	$(COMPOSE) stop

.PHONY: start
start: ## Start container yang sudah ada
	$(COMPOSE) start

.PHONY: ps
ps: ## Tampilkan status container
	$(COMPOSE) ps

.PHONY: status
status: ## Ringkasan health & port seluruh service
	@$(COMPOSE) ps --format 'table {{.Name}}\t{{.Service}}\t{{.Status}}\t{{.Ports}}'

# =============================================================================
# LOGS & OBSERVABILITY
# =============================================================================
.PHONY: logs
logs: ## Ikuti log semua service (Ctrl+C untuk keluar)
	$(COMPOSE) logs -f --tail=100

.PHONY: logs-backend
logs-backend: ## Ikuti log backend
	$(COMPOSE) logs -f --tail=100 $(BACKEND_SVC)

.PHONY: logs-frontend
logs-frontend: ## Ikuti log frontend
	$(COMPOSE) logs -f --tail=100 $(FRONTEND_SVC)

.PHONY: logs-db
logs-db: ## Ikuti log postgres
	$(COMPOSE) logs -f --tail=100 $(DB_SVC)

.PHONY: logs-redis
logs-redis: ## Ikuti log redis
	$(COMPOSE) logs -f --tail=100 $(REDIS_SVC)

.PHONY: health
health: ## Cek endpoint /health backend dan status semua container
	@echo "── Container ──"
	@$(COMPOSE) ps --format 'table {{.Name}}\t{{.Status}}'
	@echo ""
	@echo "── Backend /health ──"
	@curl -fsS http://localhost:$(BACKEND_PORT)/health && echo "" \
		|| echo "$(C_YELLOW)✖$(C_RESET) backend belum merespons di port $(BACKEND_PORT)"
	@echo ""
	@echo "── Frontend ──"
	@curl -fsS -o /dev/null -w "HTTP %{http_code}\n" http://localhost:$(FRONTEND_PORT) \
		|| echo "$(C_YELLOW)✖$(C_RESET) frontend belum merespons di port $(FRONTEND_PORT)"

# =============================================================================
# SHELL ACCESS
# =============================================================================
.PHONY: shell-backend
shell-backend: ## Masuk ke shell container backend
	$(COMPOSE) exec $(BACKEND_SVC) bash || $(COMPOSE) exec $(BACKEND_SVC) sh

.PHONY: shell-frontend
shell-frontend: ## Masuk ke shell container frontend
	$(COMPOSE) exec $(FRONTEND_SVC) sh

.PHONY: psql
psql: ## Buka psql interaktif di container postgres
	$(COMPOSE) exec $(DB_SVC) psql -U $${POSTGRES_USER:-omnigensi} -d $${POSTGRES_DB:-omnigensi}

.PHONY: redis-cli
redis-cli: ## Buka redis-cli interaktif
	$(COMPOSE) exec $(REDIS_SVC) redis-cli

# =============================================================================
# DATABASE
# =============================================================================
.PHONY: db-init
db-init: ## Inisialisasi skema database (lewat lifespan backend)
	@echo "Skema dibuat otomatis saat backend start (init_db)."
	@curl -fsS http://localhost:$(BACKEND_PORT)/health >/dev/null \
		&& echo "$(C_GREEN)✔$(C_RESET) Database siap dipakai." \
		|| { echo "$(C_YELLOW)✖$(C_RESET) Backend belum siap, jalankan: make logs-backend"; exit 1; }

.PHONY: db-seed
db-seed: ## Isi database dengan data contoh (provider/agent/workflow demo)
	$(COMPOSE) exec -T $(BACKEND_SVC) python seed.py

.PHONY: db-reset
db-reset: ## HAPUS semua data (volume postgres) lalu nyalakan ulang
	@echo "$(C_YELLOW)⚠$(C_RESET)  Ini akan menghapus SELURUH data database."
	@read -p "Lanjutkan? [y/N] " ans; [[ $$ans == [yY] ]] || { echo "Dibatalkan."; exit 1; }
	$(COMPOSE) down
	docker volume rm -f omnigensi_omnigensi_pgdata 2>/dev/null || true
	$(COMPOSE) up -d --build
	@echo "$(C_GREEN)✔$(C_RESET) Database direset."

.PHONY: db-dump
db-dump: ## Backup database ke ./backups/omnigensi-<timestamp>.sql
	@mkdir -p backups
	@ts=$$(date +%Y%m%d-%H%M%S); \
	$(COMPOSE) exec -T $(DB_SVC) pg_dump -U $${POSTGRES_USER:-omnigensi} $${POSTGRES_DB:-omnigensi} \
		> backups/omnigensi-$$ts.sql && \
	echo "$(C_GREEN)✔$(C_RESET) Backup tersimpan: backups/omnigensi-$$ts.sql"

.PHONY: db-restore
db-restore: ## Restore database dari FILE=backups/xxx.sql
	@test -n "$(FILE)" || { echo "$(C_YELLOW)✖$(C_RESET) Pemakaian: make db-restore FILE=backups/omnigensi-xxx.sql"; exit 1; }
	@test -f "$(FILE)" || { echo "$(C_YELLOW)✖$(C_RESET) File $(FILE) tidak ditemukan"; exit 1; }
	$(COMPOSE) exec -T $(DB_SVC) psql -U $${POSTGRES_USER:-omnigensi} -d $${POSTGRES_DB:-omnigensi} < $(FILE)
	@echo "$(C_GREEN)✔$(C_RESET) Restore dari $(FILE) selesai."

# =============================================================================
# MIGRATIONS (ALEMBIC)
# =============================================================================
.PHONY: migrate
migrate: ## Terapkan semua migrasi alembic (upgrade head)
	$(COMPOSE) exec -T $(BACKEND_SVC) alembic upgrade head

.PHONY: migrate-down
migrate-down: ## Rollback satu langkah migrasi
	$(COMPOSE) exec -T $(BACKEND_SVC) alembic downgrade -1

.PHONY: migrate-new
migrate-new: ## Buat migrasi baru: make migrate-new M="pesan migrasi"
	@test -n "$(M)" || { echo "$(C_YELLOW)✖$(C_RESET) Pemakaian: make migrate-new M=\"pesan migrasi\""; exit 1; }
	$(COMPOSE) exec -T $(BACKEND_SVC) alembic revision --autogenerate -m "$(M)"

.PHONY: migrate-history
migrate-history: ## Lihat riwayat migrasi
	$(COMPOSE) exec -T $(BACKEND_SVC) alembic history --verbose

# =============================================================================
# TESTING & QUALITY
# =============================================================================
.PHONY: test
test: ## Jalankan seluruh test backend (pytest)
	$(COMPOSE) exec -T $(BACKEND_SVC) python -m pytest -v

.PHONY: test-cov
test-cov: ## Jalankan test dengan laporan coverage
	$(COMPOSE) exec -T $(BACKEND_SVC) python -m pytest -v \
		--cov=app --cov-report=term-missing

.PHONY: test-file
test-file: ## Jalankan satu file test: make test-file F=tests/test_api.py
	@test -n "$(F)" || { echo "$(C_YELLOW)✖$(C_RESET) Pemakaian: make test-file F=tests/test_api.py"; exit 1; }
	$(COMPOSE) exec -T $(BACKEND_SVC) python -m pytest -v $(F)

.PHONY: check-frontend
check-frontend: ## Type-check frontend (svelte-check)
	$(COMPOSE) exec -T $(FRONTEND_SVC) pnpm run check

.PHONY: check
check: check-frontend ## Jalankan semua pemeriksaan statis

.PHONY: lint
lint: ## Validasi konfigurasi compose + cek sintaks Python
	@echo "── docker compose config ──"
	@$(COMPOSE) config --quiet && echo "$(C_GREEN)✔$(C_RESET) compose valid"
	@echo "── python syntax ──"
	@$(COMPOSE) exec -T $(BACKEND_SVC) python -B -c "import pathlib; \
files = list(pathlib.Path('app').rglob('*.py')); \
[compile(f.read_text(), str(f), 'exec') for f in files]; \
print(f'{len(files)} file OK')" && echo "$(C_GREEN)✔$(C_RESET) sintaks Python OK"

# =============================================================================
# BUILD
# =============================================================================
.PHONY: build
build: ## Build semua image
	$(COMPOSE) build

.PHONY: build-backend
build-backend: ## Build image backend saja
	$(COMPOSE) build $(BACKEND_SVC)

.PHONY: build-frontend
build-frontend: ## Build image frontend saja
	$(COMPOSE) build $(FRONTEND_SVC)

.PHONY: build-prod
build-prod: ## Build image mode production (target production)
	BACKEND_TARGET=production FRONTEND_TARGET=production $(COMPOSE) build

# =============================================================================
# PRODUCTION
# =============================================================================
.PHONY: prod-up
prod-up: ## Jalankan stack di mode production (docker-compose.prod.yml)
	$(COMPOSE_PROD) up -d --build

.PHONY: prod-down
prod-down: ## Hentikan stack production
	$(COMPOSE_PROD) down

# =============================================================================
# CLEANUP
# =============================================================================
.PHONY: clean
clean: ## Hentikan stack dan hapus container + network (volume aman)
	$(COMPOSE) down --remove-orphans
	@echo "$(C_GREEN)✔$(C_RESET) Container & network dibersihkan."

.PHONY: clean-all
clean-all: ## HAPUS container, network, image, DAN semua volume (data hilang!)
	@echo "$(C_YELLOW)⚠$(C_RESET)  Semua data volume akan dihapus permanen."
	@read -p "Lanjutkan? [y/N] " ans; [[ $$ans == [yY] ]] || { echo "Dibatalkan."; exit 1; }
	$(COMPOSE) down -v --remove-orphans --rmi local
	@echo "$(C_GREEN)✔$(C_RESET) Cleanup total selesai."

.PHONY: prune
prune: ## Bersihkan image/dangling resource Docker yang tidak terpakai
	docker system prune -f
