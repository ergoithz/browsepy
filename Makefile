.PHONY: clean

clean:
	rm -rf \
		build \
		dist \
		browsepy.egg-info
	find browsepy -type f -name "*.py[co]" -delete
	find browsepy -type d -name "__pycache__" -delete
	$(MAKE) -C doc clean
