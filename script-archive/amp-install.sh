#!/usr/bin/env bash
set -euo pipefail

# Amp CLI Binary Installation Script (EXPERIMENTAL - NOT DOCUMENTED)
# This is a secondary install script for testing binary distribution
# Downloads pre-compiled Amp CLI binary instead of using npm

# Configuration
AMP_HOME="${AMP_HOME:-$HOME/.amp}"
BIN_DIR="$AMP_HOME/bin"
STORAGE_BASE="https://static.ampcode.com"
AMP_URL="${AMP_URL:-https://ampcode.com}"
AMP_VERSION="${AMP_VERSION:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Cleanup on interrupt
cleanup() {
	echo -e "\n${YELLOW}Installation interrupted...${NC}"
	rm -f "$AMP_HOME/amp-install-"* 2>/dev/null || true
	exit 1
}

trap cleanup INT TERM

log() {
	echo -e "${BLUE}[INFO]${NC} $1" >&2
}

warn() {
	echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

error() {
	echo -e "${RED}[ERROR]${NC} $1" >&2
	exit 1
}

success() {
	echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

# Check if command exists
command_exists() {
	command -v "$1" >/dev/null 2>&1
}

# Require command to exist or exit with error
need_cmd() {
	if ! command_exists "$1"; then
		error "need '$1' (command not found)"
	fi
}

# Check all prerequisite commands upfront
check_prereqs() {
	for cmd in uname mktemp chmod mkdir rm; do
		need_cmd "$cmd"
	done

	# Check for sha256 checksum command (shasum on macOS/BSD, sha256sum on Linux)
	if command_exists shasum; then
		SHA256_CMD="shasum -a 256"
	elif command_exists sha256sum; then
		SHA256_CMD="sha256sum"
	else
		error "need 'shasum' or 'sha256sum' (command not found)"
	fi
}

# Detect target platform for CLI binary
detect_platform() {
	local platform
	platform="$(uname -s) $(uname -m)"

	case $platform in
		'Darwin x86_64')
			target=darwin-x64
			;;
		'Darwin arm64')
			target=darwin-arm64
			;;
		'Linux aarch64' | 'Linux arm64')
			target=linux-arm64
			;;
		'MINGW64'*)
			target=windows-x64
			;;
		'Linux riscv64')
			error 'Not supported on riscv64'
			;;
		'Linux x86_64' | *)
			target=linux-x64
			;;
	esac

	# Check for baseline builds on x64
	case "$target" in
		'darwin-x64')
			# Check Rosetta 2
			if [[ $(sysctl -n sysctl.proc_translated 2>/dev/null) = 1 ]]; then
				target=darwin-arm64
				log "Your shell is running in Rosetta 2. Using $target instead"
			elif [[ $(sysctl -a 2>/dev/null | grep machdep.cpu | grep AVX2) == '' ]]; then
				target="darwin-x64-baseline"
			fi
			;;
		'linux-x64')
			# Check AVX2 support
			if [[ $(grep avx2 /proc/cpuinfo 2>/dev/null) = '' ]]; then
				target="linux-x64-baseline"
			fi
			;;
		'windows-x64')
			# For Windows, default to baseline for better compatibility
			target="windows-x64-baseline"
			;;
	esac

	echo "$target"
}

# Robust downloader that handles snap curl issues
downloader() {
	local url="$1"
	local output_file="$2"

	# Check if we have a broken snap curl
	local snap_curl=0
	if command_exists curl; then
		local curl_path
		curl_path=$(command -v curl)
		if [[ "$curl_path" == *"/snap/"* ]]; then
			snap_curl=1
		fi
	fi

	# Check if we have a working (non-snap) curl
	if command_exists curl && [[ $snap_curl -eq 0 ]]; then
		curl -fsSL "$url" -o "$output_file"
	# Try wget for both no curl and the broken snap curl
	elif command_exists wget; then
		wget -q --show-progress "$url" -O "$output_file"
	# If we can't fall back from broken snap curl to wget, report the broken snap curl
	elif [[ $snap_curl -eq 1 ]]; then
		error "curl installed with snap cannot download files due to missing permissions. Please uninstall it and reinstall curl with a different package manager (e.g., apt)."
	else
		error "Neither curl nor wget found. Please install one of them."
	fi
}

# Download file with progress
download_file() {
	local url="$1"
	local output_file="$2"

	log "Downloading $(basename "$output_file")..."

	# Use secure temporary file
	local temp_file
	temp_file=$(mktemp "$(dirname "$output_file")/tmp.XXXXXX")

	# Download to temp file first, then atomic move
	downloader "$url" "$temp_file"
	mv "$temp_file" "$output_file"
}

# Verify SHA256 checksum
verify_checksum() {
	local file="$1"
	local expected_checksum="$2"

	log "Verifying checksum..."

	local actual_checksum
	actual_checksum=$($SHA256_CMD "$file" | cut -d' ' -f1)

	if [[ "$actual_checksum" != "$expected_checksum" ]]; then
		error "Checksum verification failed!\nExpected: $expected_checksum\nActual: $actual_checksum"
	fi

	success "Checksum verified"
}

# Verify signature using minisign
verify_signature() {
	local file="$1"
	local signature_url="$2"

	if ! command_exists minisign; then
		log "minisign not installed, skipping signature verification"
		return 0
	fi

	local signature_path="$AMP_HOME/amp-install-signature.minisign"
	local pubkey_path="$AMP_HOME/signing-key.pub"

	download_file "$signature_url" "$signature_path"
	download_file "$AMP_URL/.well-known/signing-key.pub" "$pubkey_path"

	if ! minisign -Vm "$file" -x "$signature_path" -p "$pubkey_path" >/dev/null 2>&1; then
		rm -f "$signature_path" "$pubkey_path"
		error "Signature verification failed! The binary may have been tampered with."
	fi

	rm -f "$signature_path" "$pubkey_path"
	success "Signature verified"
}

# Fetch latest CLI version
fetch_latest_version() {
	local version_url="$STORAGE_BASE/cli/cli-version.txt"
	local version_path="$AMP_HOME/amp-install-version.txt"

	download_file "$version_url" "$version_path"
	cat "$version_path"
	rm -f "$version_path"
}

# Install Amp CLI binary
install_amp_binary() {
	local platform="$1"
	local binary_name="amp"

	# Windows uses .exe extension
	if [[ "$platform" == *"windows"* ]]; then
		binary_name="amp.exe"
	fi

	local version
	if [[ -n "$AMP_VERSION" ]]; then
		version="$AMP_VERSION"
		log "Installing requested version: $version"
	else
		# Fetch version first to ensure consistent downloads (avoids race conditions
		# where a new version is published mid-download)
		log "Fetching latest version..."
		version=$(fetch_latest_version)
		log "Installing version: $version"
	fi

	# Use versioned URLs if available, fall back to root for backwards compatibility
	local binary_url="$STORAGE_BASE/cli/${version}/amp-${platform}"
	local checksum_url="$STORAGE_BASE/cli/${version}/${platform}-amp.sha256"
	local minisign_signature_url="$binary_url.minisig"

	# Check if versioned path exists, fall back to root path
	if ! curl -fsSL --head "$checksum_url" >/dev/null 2>&1; then
		binary_url="$STORAGE_BASE/cli/amp-${platform}"
		checksum_url="$STORAGE_BASE/cli/${platform}-amp.sha256"
		minisign_signature_url="$binary_url.minisig"
	fi

	# Add .exe for Windows downloads
	if [[ "$platform" == *"windows"* ]]; then
		binary_url="${binary_url}.exe"
	fi

	local binary_path="$BIN_DIR/$binary_name"
	local checksum_path="$AMP_HOME/amp-install-checksum.txt"

	# Download checksum first
	download_file "$checksum_url" "$checksum_path"
	local expected_checksum
	expected_checksum=$(cat "$checksum_path")

	# Download binary
	download_file "$binary_url" "$binary_path"

	# Verify checksum
	verify_checksum "$binary_path" "$expected_checksum"

	# Verify signature (optional, only if minisign is installed)
	# Disabled until release signing is enabled
	# verify_signature "$binary_path" "$minisign_signature_url"

	# Make executable
	chmod +x "$binary_path"

	# Clean up checksum file
	rm -f "$checksum_path"

	success "Amp CLI binary installed to $binary_path"
}

# Check if a directory is in PATH
dir_in_path() {
	local check_dir="$1"
	# Normalize the directory path if it exists
	if [[ -d "$check_dir" ]]; then
		check_dir=$(cd "$check_dir" 2>/dev/null && pwd) || return 1
	fi
	echo ":$PATH:" | grep -q ":$check_dir:"
}

# Try to create a symlink in a directory that's already in PATH
try_symlink_in_path() {
	local binary_name="$1"

	# Preferred directories to symlink into (in order of preference)
	local preferred_dirs=(
		"$HOME/.local/bin"
		"$HOME/bin"
		"$HOME/.bin"
	)

	for dir in "${preferred_dirs[@]}"; do
		if dir_in_path "$dir"; then
			# Directory is in PATH, try to create symlink
			mkdir -p "$dir" 2>/dev/null || continue

			local symlink_path="$dir/$binary_name"
			local target_path="$BIN_DIR/$binary_name"

			# Remove existing symlink if it points elsewhere
			if [[ -L "$symlink_path" ]]; then
				rm -f "$symlink_path"
			fi

			if ln -sf "$target_path" "$symlink_path" 2>/dev/null; then
				success "Created symlink: $symlink_path -> $target_path"
				return 0
			fi
		fi
	done

	return 1
}

# Update PATH in shell profile
update_shell_profile() {
	local binary_name="amp"

	# First, try to symlink into a directory already in PATH
	if try_symlink_in_path "$binary_name"; then
		# Symlink created, no need to modify shell profile
		return
	fi

	# Create ~/.local/bin and symlink amp there (instead of adding ~/.amp/bin to PATH)
	local local_bin_dir="$HOME/.local/bin"
	mkdir -p "$local_bin_dir" 2>/dev/null || true
	local symlink_path="$local_bin_dir/$binary_name"
	local target_path="$BIN_DIR/$binary_name"

	# Remove existing symlink if it points elsewhere
	if [[ -L "$symlink_path" ]]; then
		rm -f "$symlink_path"
	fi

	if ln -sf "$target_path" "$symlink_path" 2>/dev/null; then
		success "Created symlink: $symlink_path -> $target_path"
	else
		warn "Could not create symlink in $local_bin_dir"
		warn "Please add $BIN_DIR to your PATH manually:"
		echo "  export PATH=\"$BIN_DIR:\$PATH\""
		return
	fi

	# Fall back to modifying shell profile to add ~/.local/bin
	# Detect shell from $SHELL or default
	local default_shell="bash"
	if [[ "$(uname -s)" == "Darwin" ]]; then
		default_shell="zsh"
	fi
	local os_name
	os_name="$(uname -s)"

	local shell_name
	shell_name=$(basename "${SHELL:-$default_shell}")

	local shell_profile=""
	local path_export=""

	case "$shell_name" in
		zsh)
			shell_profile="$HOME/.zshrc"
			path_export="export PATH=\"\$HOME/.local/bin:\$PATH\""
			;;
		bash)
			if [[ "$os_name" == "Darwin" ]]; then
				if [[ -f "$HOME/.bash_profile" ]]; then
					shell_profile="$HOME/.bash_profile"
				elif [[ -f "$HOME/.bashrc" ]]; then
					shell_profile="$HOME/.bashrc"
				else
					shell_profile="$HOME/.bash_profile"
				fi
			else
				if [[ -f "$HOME/.bashrc" ]]; then
					shell_profile="$HOME/.bashrc"
				elif [[ -f "$HOME/.bash_profile" ]]; then
					shell_profile="$HOME/.bash_profile"
				else
					shell_profile="$HOME/.bashrc"
				fi
			fi
			path_export="export PATH=\"\$HOME/.local/bin:\$PATH\""
			;;
		fish)
			shell_profile="$HOME/.config/fish/config.fish"
			path_export="fish_add_path \"\$HOME/.local/bin\""
			;;
		*)
			warn "Unknown shell: $shell_name"
			warn "Please add ~/.local/bin to your PATH manually:"
			echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
			return
			;;
	esac

	# Check if ~/.local/bin is already in PATH config (ignore commented lines, match PATH assignments)
	if [[ -f "$shell_profile" ]] && grep -v '^\s*#' "$shell_profile" 2>/dev/null | grep -qE 'PATH=.*\.local/bin'; then
		log "~/.local/bin already configured in $shell_profile"
		echo ""
		log "To use amp immediately, run:"
		echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
		return
	fi

	# Ask user before modifying shell config
	local tilde_profile="${shell_profile/#$HOME/\~}"
	echo ""
	if [[ -t 0 ]]; then
		# Interactive: ask user
		read -p "Add ~/.local/bin to your PATH in $tilde_profile? [y/n] " -n 1 -r
		echo ""
		if [[ ! $REPLY =~ ^[Yy]$ ]]; then
			log "Skipped modifying shell config."
			log "To use amp, add ~/.local/bin to your PATH manually:"
			echo "  $path_export"
			return
		fi
	else
		# Non-interactive: show instructions instead
		log "Non-interactive mode: skipping shell config modification."
		log "To use amp, add ~/.local/bin to your PATH:"
		echo "  $path_export"
		return
	fi

	# Create config file if it doesn't exist
	if [[ ! -f "$shell_profile" ]]; then
		mkdir -p "$(dirname "$shell_profile")"
		touch "$shell_profile"
	fi

	# Add to PATH
	{
		echo ""
		echo "# Amp CLI"
		echo "$path_export"
	} >> "$shell_profile"

	success "Added ~/.local/bin to PATH in $tilde_profile"
	echo ""
	log "To use amp immediately, run:"
	echo "  $path_export"
}

# Main installation
main() {
	log "Starting Amp CLI binary installation..."

	# Check prerequisites
	check_prereqs

	# Create directories
	mkdir -p "$BIN_DIR"

	# Detect platform
	local platform
	platform=$(detect_platform)
	log "Detected platform: $platform"

	# Install binary
	install_amp_binary "$platform"

	# Update shell profile
	update_shell_profile

	echo ""
	success "Amp CLI installed successfully!"
	log "Run 'amp --help' to get started"
	log "Visit $AMP_URL for documentation"
}

main "$@"
