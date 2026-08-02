package tech.scaleag.nexstep.util;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/** Writes user-requested exports to Android's public Downloads collection. */
public final class FileExporter {

    private FileExporter() {
    }

    public static Uri saveJson(Context context, String prefix, JSONObject data)
        throws IOException {
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
        return save(
            context,
            prefix + "_" + timestamp + ".json",
            "application/json",
            data.toString().getBytes(StandardCharsets.UTF_8)
        );
    }

    public static Uri saveLeadBoardExcel(
        Context context,
        JSONArray leads,
        boolean french
    ) throws IOException {
        StringBuilder xml = new StringBuilder();
        xml.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
            .append("<?mso-application progid=\"Excel.Sheet\"?>")
            .append("<Workbook xmlns=\"urn:schemas-microsoft-com:office:spreadsheet\" ")
            .append("xmlns:ss=\"urn:schemas-microsoft-com:office:spreadsheet\">")
            .append("<Worksheet ss:Name=\"Lead Board\"><Table>");
        appendRow(xml, new String[] {
            french ? "Prospect" : "Prospect",
            french ? "Contacts" : "Contacts",
            french ? "Prochaine action" : "Next action",
            french ? "Échéance" : "Due date",
            french ? "Urgence" : "Urgency",
            french ? "Agent" : "Agent",
            french ? "Dernier commentaire" : "Latest comment"
        });
        for (int index = 0; index < leads.length(); index += 1) {
            JSONObject lead = leads.optJSONObject(index);
            if (lead == null) continue;
            appendRow(xml, new String[] {
                lead.optString("name"),
                lead.optString("contactsText"),
                lead.optString("nextActionTitle"),
                lead.optString("nextDueDate"),
                lead.optString("urgencyLabel"),
                lead.optString("ownerName"),
                lead.optString("latestComment")
            });
        }
        xml.append("</Table></Worksheet></Workbook>");
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
        return save(
            context,
            "NexStep_Lead_Board_" + timestamp + ".xls",
            "application/vnd.ms-excel",
            xml.toString().getBytes(StandardCharsets.UTF_8)
        );
    }

    public static Uri saveIcs(
        Context context,
        String title,
        String description,
        String dueDate
    ) throws IOException {
        LocalDate startDate = LocalDate.parse(dueDate);
        String compactDate = startDate.format(DateTimeFormatter.BASIC_ISO_DATE);
        String compactEndDate = startDate.plusDays(1).format(DateTimeFormatter.BASIC_ISO_DATE);
        String escapedTitle = icsEscape(title);
        String escapedDescription = icsEscape(description);
        String content = "BEGIN:VCALENDAR\r\n"
            + "VERSION:2.0\r\n"
            + "PRODID:-//scale.ag//NexStep//FR\r\n"
            + "BEGIN:VEVENT\r\n"
            + "UID:" + java.util.UUID.randomUUID() + "@nexstep.scale-ag.tech\r\n"
            + "DTSTART;VALUE=DATE:" + compactDate + "\r\n"
            + "DTEND;VALUE=DATE:" + compactEndDate + "\r\n"
            + "SUMMARY:" + escapedTitle + "\r\n"
            + "DESCRIPTION:" + escapedDescription + "\r\n"
            + "BEGIN:VALARM\r\n"
            + "TRIGGER:-P1D\r\n"
            + "ACTION:DISPLAY\r\n"
            + "DESCRIPTION:" + escapedTitle + "\r\n"
            + "END:VALARM\r\n"
            + "END:VEVENT\r\n"
            + "END:VCALENDAR\r\n";
        return save(
            context,
            "NexStep_" + compactDate + ".ics",
            "text/calendar",
            content.getBytes(StandardCharsets.UTF_8)
        );
    }

    private static Uri save(
        Context context,
        String fileName,
        String mimeType,
        byte[] data
    ) throws IOException {
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
        values.put(MediaStore.MediaColumns.MIME_TYPE, mimeType);
        values.put(
            MediaStore.MediaColumns.RELATIVE_PATH,
            Environment.DIRECTORY_DOWNLOADS + "/NexStep"
        );
        ContentResolver resolver = context.getContentResolver();
        Uri uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
        if (uri == null) throw new IOException("Unable to create export.");
        try (OutputStream output = resolver.openOutputStream(uri)) {
            if (output == null) throw new IOException("Unable to open export.");
            output.write(data);
        } catch (IOException exception) {
            resolver.delete(uri, null, null);
            throw exception;
        }
        return uri;
    }

    private static void appendRow(StringBuilder xml, String[] values) {
        xml.append("<Row>");
        for (String value : values) {
            xml.append("<Cell><Data ss:Type=\"String\">")
                .append(xmlEscape(value))
                .append("</Data></Cell>");
        }
        xml.append("</Row>");
    }

    private static String xmlEscape(String value) {
        return String.valueOf(value == null ? "" : value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;");
    }

    private static String icsEscape(String value) {
        return String.valueOf(value == null ? "" : value)
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(",", "\\,")
            .replace(";", "\\;");
    }
}
