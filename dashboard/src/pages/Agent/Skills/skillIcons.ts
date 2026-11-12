import synology from "../../../assets/connectors/synology-nas.png";
import audio from "../../../assets/synology-skills/audio.png";
import calendar from "../../../assets/synology-skills/calendar.png";
import containers from "../../../assets/synology-skills/containers.png";
import downloads from "../../../assets/synology-skills/downloads.png";
import files from "../../../assets/synology-skills/files.png";
import notes from "../../../assets/synology-skills/notes.png";
import packages from "../../../assets/synology-skills/packages.webp";
import photos from "../../../assets/synology-skills/photos.png";
import vmm from "../../../assets/synology-skills/vmm.png";

// Synology Download Center thumbnails, plus the DSM 7 Package Center icon from my-nas.
const synologySkillIcons = new Map([
  ["synology-nas", synology],
  ["synology-audio", audio],
  ["synology-calendar", calendar],
  ["synology-containers", containers],
  ["synology-downloads", downloads],
  ["synology-files", files],
  ["synology-notes", notes],
  ["synology-packages", packages],
  ["synology-photos", photos],
  ["synology-vmm", vmm],
]);

export function resolveSkillIconUrl(skill: {
  slug?: string;
  name: string;
  icon_url?: string | null;
}): string | undefined {
  return (
    skill.icon_url?.trim() || synologySkillIcons.get(skill.slug ?? skill.name)
  );
}
