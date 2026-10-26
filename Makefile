NAME          = mystery-auctions
COMPOSE       = docker compose
COMPOSE_FILE  = docker-compose.yml
URL           = https://localhost:8443

# -------- colors -------- #
LAVENDER    = \033[38;5;147m
PINK        = \033[38;5;218m
GREEN       = \033[38;5;114m
RESET       = \033[0m
ARROW       = ✔

# -------- rules -------- #
all: env up

# creates .env from the repo's actual template if missing, with a real
# random Django secret key — never overwrites an existing .env
env:
	@if [ ! -f .env ]; then \
		echo "$(LAVENDER)Creating .env from the repo template...$(RESET)"; \
		if [ -f .env.example ]; then \
			cp .env.example .env; \
		elif [ -f backend/.env.local ]; then \
			cp backend/.env.local .env; \
		else \
			printf '%s\n' \
				"DJANGO_SECRET_KEY=$$(openssl rand -hex 32)" \
				"DJANGO_DEBUG=True" \
				"DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend,nginx" \
				"DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443" \
				"DJANGO_CORS_ALLOWED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443" \
				"POSTGRES_DB=transcendence_db" \
				"POSTGRES_USER=transcendence_user" \
				"POSTGRES_PASSWORD=transcendence_password" \
				"POSTGRES_HOST=db" \
				"POSTGRES_PORT=5432" \
				"REDIS_URL=redis://redis:6379/0" \
				"HTTPS_PORT=8443" > .env; \
		fi; \
		if ! grep -q '^POSTGRES_HOST=' .env; then printf '%s\n' 'POSTGRES_HOST=db' >> .env; fi; \
		if ! grep -q '^REDIS_URL=' .env; then printf '%s\n' 'REDIS_URL=redis://redis:6379/0' >> .env; fi; \
		if ! grep -q '^DJANGO_SECRET_KEY=' .env || [ -z "$$(grep '^DJANGO_SECRET_KEY=' .env | cut -d= -f2-)" ]; then \
			SECRET=$$(openssl rand -hex 32); \
			sed -i.bak "s/^DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$$SECRET/" .env && rm -f .env.bak; \
		fi; \
		echo "$(GREEN).env created $(ARROW) edit it if you want custom values$(RESET)"; \
	else \
		echo "$(LAVENDER).env already exists, leaving it alone$(RESET)"; \
	fi

up: env
	@echo "$(LAVENDER)Building and starting $(NAME)...$(RESET)"
	@$(COMPOSE) -f $(COMPOSE_FILE) up --build -d
	@echo "$(GREEN)$(NAME) is up $(ARROW) $(URL)$(RESET)"

# same as up, but stays attached with logs streaming, ctrl-c to stop
run: env
	@echo "$(LAVENDER)Building and starting $(NAME) (foreground)...$(RESET)"
	@$(COMPOSE) -f $(COMPOSE_FILE) up --build

down:
	@echo "$(PINK)Stopping $(NAME)...$(RESET)"
	@$(COMPOSE) -f $(COMPOSE_FILE) down
	@echo "$(PINK)Done $(ARROW)$(RESET)"

restart: down up

logs:
	@$(COMPOSE) -f $(COMPOSE_FILE) logs -f

ps:
	@$(COMPOSE) -f $(COMPOSE_FILE) ps

# -------- backend verification (from the README) -------- #
check:
	@$(COMPOSE) -f $(COMPOSE_FILE) exec backend python manage.py check

test:
	@$(COMPOSE) -f $(COMPOSE_FILE) exec backend python manage.py test apps

migrations-check:
	@$(COMPOSE) -f $(COMPOSE_FILE) exec backend python manage.py makemigrations --check --dry-run

migrate:
	@$(COMPOSE) -f $(COMPOSE_FILE) exec backend python manage.py migrate

superuser:
	@$(COMPOSE) -f $(COMPOSE_FILE) exec backend python manage.py createsuperuser

seed:
	@$(COMPOSE) -f $(COMPOSE_FILE) exec backend python manage.py seed_demo

# -------- cleanup -------- #
# stop containers and drop networks, keep images/volumes (fast rebuilds)
clean:
	@echo "$(PINK)Removing containers and networks...$(RESET)"
	@$(COMPOSE) -f $(COMPOSE_FILE) down --remove-orphans
	@echo "$(PINK)Done $(ARROW)$(RESET)"

# also drop images and volumes (full reset incl. the database — next
# 'make' rebuilds and reseeds from scratch)
fclean: clean
	@echo "$(PINK)Removing images and volumes...$(RESET)"
	@$(COMPOSE) -f $(COMPOSE_FILE) down --rmi all --volumes --remove-orphans
	@echo "$(PINK)Done $(ARROW)$(RESET)"

re: fclean up

# nuke everything docker-related on the machine, not just this project
prune:
	@echo "$(PINK)Pruning all unused docker data...$(RESET)"
	@docker system prune -af --volumes
	@echo "$(PINK)Done $(ARROW)$(RESET)"

.PHONY: all env up run down restart logs ps check test migrations-check migrate superuser seed clean fclean re prune