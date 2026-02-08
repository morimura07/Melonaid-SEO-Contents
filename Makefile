# Makefile for auto-setup depending on OS

OS := $(shell uname -s)

setup:
ifeq ($(OS),Linux)
	chmod +x setup.sh && ./setup.sh
else ifeq ($(OS),Darwin)
	chmod +x setup.sh && ./setup.sh
else
	@echo "Assuming Windows..."
	@setup.bat
endif