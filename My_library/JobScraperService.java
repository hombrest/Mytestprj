package com.example.service;

import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.poi.openxml4j.exceptions.InvalidFormatException;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Service
public class JobScraperService {
    private static final Logger logger = LoggerFactory.getLogger(JobScraperService.class);

    @Autowired
    private CloseableHttpClient httpClient;

    @Autowired
    private ExcelService excelService;

    private static final String BASE_URL = "https://www.infotech.com.hk/itjs/job/fe-view.do?method=feView&jjKey=";
    private static final String SEARCH_URL = "https://infotech.com.hk/itjs/job/fe-search.do?method=feList&sortByField=jjm_activedate&sortByOrder=DESC";
    private static final int TIMEOUT_MILLISECONDS = 60000;

    private static final String[] EXCLUDED_FIELDS = {
            "Monthly Salary Range HK$", "Payroll", "Apply To", "Direct Line", "Employer Business"
    };

    private static final String DUTIES_FIELD = "Duties";
    private static final String REQUIREMENTS_FIELD = "Requirements";
    private static final String JOB_TITLE_CATEGORY_FIELD = "Job Title/ Category";
    private static final String CONTRACT_PERIOD_FIELD = "Contract Period";

    @Async
    @Scheduled(fixedDelay = 86400000) // Run daily
    public CompletableFuture<String> scrapeJobs() {
        logger.info("Starting job scraping process...");

        Set<String> searchKeys = new HashSet<>();
        Set<String> existingKeys;
        try {
            existingKeys = excelService.getExistingJobKeys();
        } catch (IOException e) {
            logger.error("Failed to read existing job keys from Excel file", e);
            return CompletableFuture.completedFuture("Failed to read existing job keys from Excel file");
        }

        List<Map<String, String>> newJobs = new ArrayList<>();

        // Fetch job keys from search page
        try {
            Document doc = Jsoup.connect(SEARCH_URL)
                    .timeout(TIMEOUT_MILLISECONDS)
                    .get();

            Elements links = doc.select("a");
            for (Element link : links) {
                String text = link.text();
                if (text.contains("Contract") && text.contains("Bid")) {
                    String href = link.attr("href");
                    int keyPos = href.indexOf("jjKey=");
                    if (keyPos >= 0) {
                        String key = href.substring(keyPos + 6);
                        searchKeys.add(key);
                        logger.debug("Found job key: {}", key);
                    }
                }
            }
        } catch (IOException e) {
            logger.error("Failed to fetch job keys from search page", e);
            return CompletableFuture.completedFuture("Failed to fetch job keys from search page");
        }

        int numOfNewJobs = 0;
        // Process each job
        for (String key : searchKeys) {
            //                logger.debug("Skipping existing job with key: {}", key);
            if (!existingKeys.contains(key)) {
                numOfNewJobs++;
                logger.info("Processing job # {} with key: {}", numOfNewJobs, key);
                Map<String, String> job = extractJobDetail(BASE_URL + key);
                if (job != null) {
                    newJobs.add(job);
                    logger.debug("Extracted job details: {}", job);
                }
            }
        }

        if (!newJobs.isEmpty()) {
            try {
                excelService.writeNewJobs(newJobs);
                logger.info("Successfully wrote {} new jobs to Excel file", newJobs.size());
            } catch (IOException e) {
                logger.error("Failed to write new jobs to Excel file", e);
            } catch (InvalidFormatException e) {
                throw new RuntimeException(e);
            }
        } else {
            logger.info("No new jobs found to write to Excel file");
        }

        logger.info("Job scraping process completed.");

        // Get the current time
        LocalDateTime currentTime = LocalDateTime.now();

        // Format the current time
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
        String formattedTime = currentTime.format(formatter);

        if(numOfNewJobs ==0) {
            return CompletableFuture.completedFuture("No new jobs found at " + formattedTime);
        }else{
            return CompletableFuture.completedFuture("Found " + numOfNewJobs + " new jobs at " + formattedTime);
        }

    }

    private Map<String, String> extractJobDetail(String jobUrl) {
        logger.debug("Extracting job details from URL: {}", jobUrl);

        Map<String, String> data = new LinkedHashMap<>();
        try {
            Document doc = Jsoup.connect(jobUrl)
                    .timeout(TIMEOUT_MILLISECONDS)
                    .get();

            Element form = Optional.ofNullable(doc.selectFirst("form[name=jobForm]"))
                    .orElseThrow(() -> new IllegalStateException("Form not found"));

            form.select("tr").stream()
                    .map(row -> row.select("td"))
                    .filter(columns -> columns.size() == 2)
                    .forEach(columns -> processColumns(columns, data));

            return data;
        } catch (Exception e) {
            logger.error("Error extracting job details from {}: ", jobUrl, e);
            return null;
        }
    }

    private static void processColumns(Elements columns, Map<String, String> data) {
        if (columns == null || columns.size() < 2) {
            return;
        }

        String fieldName = columns.get(0).text().trim();
        String fieldData = extractFieldData(columns, fieldName);

        if (!fieldName.isEmpty() && !Arrays.asList(EXCLUDED_FIELDS).contains(fieldName)) {
            data.put(fieldName, fieldData);

            switch (fieldName) {
                case DUTIES_FIELD:
                    data.put("B/D", extractBd(fieldData));
                    break;
                case JOB_TITLE_CATEGORY_FIELD:
                    processTitle(fieldData, data);
                    break;
                case CONTRACT_PERIOD_FIELD:
                    processContractPeriod(fieldData, data);
                    break;
            }
        }
    }

    private static String extractTitle(String text) {
        int index = text.indexOf('(');
        if (index == -1) {
            logger.debug("No title abbreviation found in text: {}", text);
            return null;
        }
        String prefix = text.substring(0, index).trim();
        return Arrays.stream(prefix.split(" "))
                .map(word -> word.substring(0, 1))
                .collect(Collectors.joining());
    }

    private static String extractBd(String text) {
        int serveIndex = text.indexOf("serve the");
        if (serveIndex == -1) {
            logger.debug("No 'serve the' keyword found in text: {}", text);
            return null;
        }
        String substring = text.substring(serveIndex + 10);
        int newlineIndex = substring.indexOf("\n");
        if (newlineIndex == -1) {
            logger.debug("No space found after 'serve the' in text: {}", text);
            return null;
        }
        return substring.substring(0, newlineIndex).replace(";", "").trim();
    }

    private static String extractFieldData(Elements columns, String fieldName) {
        if (DUTIES_FIELD.equals(fieldName) || REQUIREMENTS_FIELD.equals(fieldName)) {
            return columns.get(1).html()
                    .replaceAll("<br\\s*/*>", "\n")
                    .replaceAll("&nbsp;", " ")
                    .replaceAll("&amp;", "&")
                    .trim();
        } else {
            return columns.get(1).text().trim();
        }
    }

    private static void processTitle(String fieldData, Map<String, String> data) {
        String[] result = new String[2];

        try {
            // Get the part before the bracket
            String beforeBracket = fieldData.substring(0, fieldData.indexOf("(")).trim();

            // Get the abbreviation by taking first character of each word
            String abbreviation = Arrays.stream(beforeBracket.split("\\s+"))
                    .map(word -> String.valueOf(word.charAt(0)))
                    .collect(Collectors.joining());

            // Get the number including hyphen using regex
            Pattern pattern = Pattern.compile("\\d+\\-\\d+");
            Matcher matcher = pattern.matcher(fieldData);
            String number = matcher.find() ? matcher.group() : "";

            result[0] = abbreviation;
            result[1] = number;
        } catch (Exception e) {
            result[0] = "";
            result[1] = "";
        }

        data.put("Title", result[0]);
        data.put("Bid Ref", result[1]);

    }

    private static void processContractPeriod(String fieldData, Map<String, String> data) {
        String[] contractDates = fieldData.split(" to | \\(");
        data.put("Contract Start Date", contractDates[0].trim());
        data.put("Contract End Date", contractDates[1].trim());
        data.put("Contract Duration", contractDates[2].replace(")", "").trim());
    }
}