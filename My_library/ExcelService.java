package com.example.service;

import com.example.model.JobDetail;
import org.apache.poi.openxml4j.exceptions.InvalidFormatException;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;

import java.io.*;
import java.util.*;

import static org.apache.poi.ss.usermodel.CellType.NUMERIC;

@Service
public class ExcelService {
    private static final String FILE_PATH = "job_detail.xlsx";
    private static final String SHEET_NAME = "Details";

    public Set<String> getExistingJobKeys() throws IOException {
        Set<String> keys = new HashSet<>();
        File file = new File(FILE_PATH);
        if (!file.exists()) return keys;

        try (Workbook workbook = new XSSFWorkbook(file)) {
            Sheet sheet = workbook.getSheet(SHEET_NAME);
            if (sheet == null) return keys;
            for (Row row : sheet) {
                Cell cell = row.getCell(0); // Assuming Job Key is first column
                if (cell != null) {
                    if (cell.getCellType() == NUMERIC) {
                        keys.add(String.valueOf((int) cell.getNumericCellValue()));
                    }
                    else {
                        keys.add(cell.getStringCellValue());
                    }

                }
            }
        } catch (InvalidFormatException e) {
            throw new RuntimeException(e);
        }
        return keys;
    }
    public void writeNewJobs(List<Map<String, String>> rows) throws IOException, InvalidFormatException {
        if (rows == null || rows.isEmpty()) {
            return;
        }

        File file = new File(FILE_PATH);
        Workbook workbook;
        Sheet sheet;
        int lastRowNum;
        List<String> headers;

        try (FileInputStream fis = new FileInputStream(file)) {
            workbook = new XSSFWorkbook(fis);
            sheet = workbook.getSheet(SHEET_NAME);
            lastRowNum = sheet.getLastRowNum();
        } catch (FileNotFoundException e) {
            workbook = new XSSFWorkbook();
            sheet = workbook.createSheet(SHEET_NAME);
            lastRowNum = 0;
        }

        Row firstRow = sheet.getRow(0);
        headers = (firstRow != null) ? readHeaders(firstRow) : new ArrayList<>(rows.get(0).keySet());

        writeDataToSheet(sheet, rows, headers, lastRowNum);

        try (FileOutputStream fos = new FileOutputStream(file)) {
            workbook.write(fos);
        }
        workbook.close();
    }

    private List<String> readHeaders(Row firstRow) {
        List<String> headers = new ArrayList<>();
        for (Cell cell : firstRow) {
            headers.add(cell.getStringCellValue());
        }
        return headers;
    }

    private void writeDataToSheet(Sheet sheet, List<Map<String, String>> rows, List<String> headers, int lastRowNum) {
        for (int i = 0; i < rows.size(); i++) {
            Row row = sheet.createRow(lastRowNum + i + 1);
            Map<String, String> rowData = rows.get(i);
            int cellIndex = 0;
            for (String header : headers) {
                Cell cell = row.createCell(cellIndex++);
                cell.setCellValue(rowData.getOrDefault(header, ""));
            }
        }
    }
}
