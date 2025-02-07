import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.*;

public class JobScraper {

    public static void main(String[] args) {
        String url = "https://infotech.com.hk/itjs/job/fe-search.do?method=feList&sortByField=jjm_activedate&sortByOrder=DESC";
        Set<String> searchKeys = new HashSet<>();

        try {
            Document doc = Jsoup.connect(url).get();
            Elements links = doc.select("a");

            for (Element link : links) {
                if (link.text().contains("Contract") && link.text().contains("Bid")) {
                    String subUrl = link.attr("href");
                    int keyPos = subUrl.indexOf("jjKey=");
                    if (keyPos >= 0) {
                        searchKeys.add(subUrl.substring(keyPos + "jjKey=".length()));
                    }
                }
            }

            String filePath = "job_detail.xlsx";
            List<Map<String, String>> existingData = readExcel(filePath);
            Set<String> existingKeys = new HashSet<>();
            for (Map<String, String> entry : existingData) {
                existingKeys.add(entry.get("Job Key No"));
            }

            List<Map<String, String>> newRows = new ArrayList<>();
            for (String key : searchKeys) {
                if (!existingKeys.contains(key)) {
                    Map<String, String> job = extractJobDetail("https://www.infotech.com.hk/itjs/job/fe-view.do?method=feView&jjKey=" + key);
                    if (job != null) {
                        newRows.add(job);
                    }
                }
            }

            if (!newRows.isEmpty()) {
                existingData.addAll(newRows);
                writeExcel(filePath, existingData);
            } else {
                System.out.println("No new job found");
            }

        } catch (IOException e) {
            System.err.println("Error: " + e.getMessage());
        }
    }

    private static Map<String, String> extractJobDetail(String jobUrl) {
        try {
            Document doc = Jsoup.connect(jobUrl).get();
            Element form = doc.selectFirst("form[name=jobForm]");

            if (form == null) {
                System.out.println("Form named 'jobForm' not found.");
                return null;
            }

            Map<String, String> data = new HashMap<>();
            Elements rows = form.select("tr");
            for (Element row : rows) {
                Elements columns = row.select("td");
                if (columns.size() == 2) {
                    String fieldName = columns.get(0).text().trim();
                    String fieldData = columns.get(1).text().trim();

                    if (!Arrays.asList("Monthly Salary Range HK$", "Payroll", "Apply To", "Direct Line", "Employer Business").contains(fieldName)) {
                        data.put(fieldName, fieldData);
                        if ("Duties".equals(fieldName)) {
                            data.put("B/D", extractBD(fieldData));
                        }
                        if ("Job Title/ Category".equals(fieldName)) {
                            data.put("Title", extractTitle(fieldData));
                        }
                    }
                }
            }
            return data;

        } catch (IOException e) {
            System.err.println("Error in extractJobDetail: " + e.getMessage());
            return null;
        }
    }

    private static String extractTitle(String text) {
        int keywordIndex = text.indexOf('(');
        if (keywordIndex != -1) {
            String extractedString = text.substring(0, keywordIndex).trim();
            if (!extractedString.isEmpty()) {
                StringBuilder abbreviation = new StringBuilder();
                for (String word : extractedString.split(" ")) {
                    abbreviation.append(word.charAt(0));
                }
                return abbreviation.toString();
            }
        }
        return null;
    }

    private static String extractBD(String text) {
        int keywordIndex1 = text.indexOf("serve the");
        if (keywordIndex1 != -1) {
            int keywordIndex2 = text.indexOf("\n", keywordIndex1);
            if (keywordIndex2 != -1) {
                return text.substring(keywordIndex1 + "serve the ".length(), keywordIndex2).trim().replace(";", "");
            }
        }
        return null;
    }

    private static List<Map<String, String>> readExcel(String filePath) {
        List<Map<String, String>> data = new ArrayList<>();
        try (FileInputStream fis = new FileInputStream(new File(filePath));
             Workbook workbook = new XSSFWorkbook(fis)) {

            Sheet sheet = workbook.getSheet("Details");

            Row headerRow = sheet.getRow(0);
            if (headerRow == null) return data;

            List<String> headers = new ArrayList<>();
            for (Cell cell : headerRow) {
                headers.add(cell.getStringCellValue());
            }

            for (int i = 1; i <= sheet.getLastRowNum(); i++) {
                Row row = sheet.getRow(i);
                if (row == null) continue;

                Map<String, String> rowData = new HashMap<>();
                for (int j = 0; j < headers.size(); j++) {
                    Cell cell = row.getCell(j);
                    rowData.put(headers.get(j), cell != null ? cell.getStringCellValue() : "");
                }
                data.add(rowData);
            }

        } catch (IOException e) {
            System.err.println("Error reading Excel file: " + e.getMessage());
        }
        return data;
    }

    private static void writeExcel(String filePath, List<Map<String, String>> data) {
        try (Workbook workbook = new XSSFWorkbook()) {
            Sheet sheet = workbook.createSheet("Details");

            if (data.isEmpty()) return;

            // Create header row
            Row headerRow = sheet.createRow(0);
            List<String> headers = new ArrayList<>(data.get(0).keySet());
            for (int i = 0; i < headers.size(); i++) {
                Cell cell = headerRow.createCell(i);
                cell.setCellValue(headers.get(i));
            }

            // Create data rows
            for (int i = 0; i < data.size(); i++) {
                Row row = sheet.createRow(i + 1);
                Map<String, String> rowData = data.get(i);
                for (int j = 0; j < headers.size(); j++) {
                    Cell cell = row.createCell(j);
                    cell.setCellValue(rowData.get(headers.get(j)));
                }
            }

            try (FileOutputStream fos = new FileOutputStream(new File(filePath))) {
                workbook.write(fos);
            }

        } catch (IOException e) {
            System.err.println("Error writing Excel file: " + e.getMessage());
        }
    }
}
