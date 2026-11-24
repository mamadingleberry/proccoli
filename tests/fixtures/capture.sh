#!/usr/bin/env bash
# Capture the /proc and /sys files Proccoli reads into a fixture tree, so tests
# can run against this machine's layout without its hardware.
#
#   tests/fixtures/capture.sh NAME        -> tests/fixtures/NAME/
#
# Sysfs symlinks to device directories (/sys/block/X, /sys/class/net/X,
# hwmonN, ...) become real directories in the fixture. Links whose *target
# name* matters (device/driver) stay symlinks with the original target text.
#
# Privacy: fixtures may be published. MAC addresses are replaced by
# locally-administered placeholders, and serial numbers, hostnames and
# DMI data are never copied. Review the tree before committing it.
set -euo pipefail

name=${1:?usage: $0 NAME}
here=$(cd "$(dirname "$0")" && pwd)
out="$here/$name"
if [[ -e $out ]]; then
    echo "$out already exists; remove it first" >&2
    exit 1
fi

copy_file() {  # copy_file /abs/path [dest-abs-path]
    local src=$1 dst=${2:-$1}
    [[ -f $src && -r $src ]] || return 0
    mkdir -p "$out$(dirname "$dst")"
    cat "$src" > "$out$dst" 2>/dev/null || rm -f "$out$dst"
}

copy_link() {  # keep a symlink, with its original (relative) target text
    local src=$1 dst=${2:-$1}
    [[ -L $src ]] || return 0
    mkdir -p "$out$(dirname "$dst")"
    ln -sfn "$(readlink "$src")" "$out$dst"
}

copy_attrs() {  # copy_attrs /src/dir /dst/dir attr...
    local src=$1 dst=$2
    shift 2
    local a
    for a in "$@"; do copy_file "$src/$a" "$dst/$a"; done
}

copy_hwmon() {  # copy_hwmon /src/hwmonN /dst/hwmonN
    local src=$1 dst=$2 f
    copy_file "$src/name" "$dst/name"
    for f in "$src"/temp*_input "$src"/temp*_label "$src"/temp*_crit \
             "$src"/power*_input "$src"/power*_average "$src"/power*_cap \
             "$src"/power*_cap_max "$src"/power*_label "$src"/energy*_input \
             "$src"/in*_input "$src"/fan*_input; do
        [[ -e $f ]] && copy_file "$f" "$dst/$(basename "$f")"
    done
    return 0
}

mac_counter=0
scrub_mac() {  # replace a captured MAC address file with a placeholder
    local f=$out$1
    [[ -f $f ]] || return 0
    mac_counter=$((mac_counter + 1))
    printf '02:00:00:00:00:%02x\n' "$mac_counter" > "$f"
}

# --- /proc -----------------------------------------------------------------
for f in stat meminfo cpuinfo uptime diskstats loadavg net/dev \
         sys/kernel/perf_event_paranoid; do
    copy_file "/proc/$f"
done

# --- Memory modules (udev's copy of SMBIOS type 17; serials removed) -------
udev_dmi="/run/udev/data/+dmi:id"
if [[ -f $udev_dmi ]]; then
    mkdir -p "$OUT/run/udev/data"
    grep '^E:MEMORY' "$udev_dmi" | grep -v 'SERIAL\|ASSET\|PART_NUMBER' \
        > "$OUT$udev_dmi" || true
fi

# --- CPU ---------------------------------------------------------------------
copy_attrs /sys/devices/system/cpu /sys/devices/system/cpu online possible present
for c in /sys/devices/system/cpu/cpu[0-9]*; do
    copy_attrs "$c/cpufreq" "$c/cpufreq" scaling_cur_freq scaling_max_freq \
        cpuinfo_max_freq cpuinfo_min_freq scaling_driver
    copy_attrs "$c/topology" "$c/topology" physical_package_id core_id \
        thread_siblings_list die_id
done

# --- hwmon (CPU and other sensors) ------------------------------------------
for h in /sys/class/hwmon/hwmon*; do
    copy_hwmon "$h" "$h"
done

# --- drives ------------------------------------------------------------------
for b in /sys/block/*; do
    n=$(basename "$b")
    case $n in loop*|ram*) continue ;; esac
    copy_attrs "$b" "$b" stat size removable ro capability ext_range
    copy_attrs "$b/queue" "$b/queue" rotational logical_block_size
    copy_attrs "$b/device" "$b/device" model vendor type transport
    copy_attrs "$b/dm" "$b/dm" name
    copy_link "$b/device/driver"
done

# --- network -----------------------------------------------------------------
for i in /sys/class/net/*; do
    copy_attrs "$i" "$i" type operstate speed mtu carrier address uevent
    scrub_mac "$i/address"
    copy_attrs "$i/statistics" "$i/statistics" rx_bytes tx_bytes
    # Empty directories don't survive git: mark them with a file.
    [[ -d $i/wireless ]] && mkdir -p "$out$i/wireless" && touch "$out$i/wireless/.fixture-keep"
    if [[ -e $i/device ]]; then
        mkdir -p "$out$i/device"
        copy_attrs "$i/device" "$i/device" vendor device subsystem_vendor \
            subsystem_device uevent
        copy_link "$i/device/driver"
    fi
done

# --- GPUs (DRM) --------------------------------------------------------------
for c in /sys/class/drm/card[0-9]; do
    copy_attrs "$c" "$c" gt_cur_freq_mhz gt_act_freq_mhz gt_min_freq_mhz \
        gt_max_freq_mhz gt_RP0_freq_mhz gt_RPn_freq_mhz
    copy_attrs "$c/device" "$c/device" vendor device subsystem_vendor \
        subsystem_device uevent boot_vga current_link_speed current_link_width \
        max_link_speed max_link_width gpu_busy_percent mem_info_vram_total \
        mem_info_vram_used mem_info_gtt_total mem_info_gtt_used pp_dpm_sclk \
        pp_dpm_mclk power_dpm_force_performance_level
    copy_link "$c/device/driver"
    for n in "$c"/device/drm/*; do      # card and render nodes of this GPU
        [[ -e $n/dev ]] && copy_file "$n/dev"
    done
    for h in "$c"/device/hwmon/hwmon*; do
        [[ -d $h ]] && copy_hwmon "$h" "$c/device/hwmon/$(basename "$h")"
    done
    # xe / i915 per-GT frequency directories
    for g in "$c"/device/tile*/gt* "$c"/gt/gt*; do
        [[ -d $g ]] || continue
        for f in "$g"/freq0/* "$g"/rps_*_freq_mhz; do
            [[ -f $f ]] && copy_file "$f"
        done
    done
done
for r in /sys/class/drm/renderD*; do
    copy_file "$r/dev"
done

# --- batteries and power supplies ---------------------------------------------
for p in /sys/class/power_supply/*; do
    copy_attrs "$p" "$p" type online status capacity capacity_level \
        power_now energy_now energy_full energy_full_design charge_now \
        charge_full charge_full_design current_now voltage_now \
        voltage_min_design cycle_count technology manufacturer model_name scope
done

echo "Captured into $out"
echo "Review it before committing (grep for anything personal)."
