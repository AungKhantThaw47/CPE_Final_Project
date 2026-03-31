/**
 * Shared GCS (Google Cloud Storage) utility functions for all components
 */

const { Storage } = require('@google-cloud/storage');
const fs = require('fs');
const path = require('path');

/**
 * Upload a file to Google Cloud Storage
 * 
 * @param {string} localFilePath - Path to the local file to upload
 * @param {string} destinationPath - Destination path in GCS bucket (e.g., 'dvb/2026-01-28/article.txt')
 * @returns {Promise<Object>} Upload status information
 */
async function uploadFileToGCS(localFilePath, destinationPath) {
    const bucketName = process.env.GCS_BUCKET;
    
    if (!bucketName) {
        console.log('⚠️  GCS_BUCKET environment variable not set');
        console.log('⚠️  Skipping GCS upload');
        return { status: 'skipped', reason: 'GCS_BUCKET not set' };
    }

    try {
        // Initialize GCS client (uses service account from Cloud Run)
        const storage = new Storage();
        const bucket = storage.bucket(bucketName);
        
        // Upload file
        await bucket.upload(localFilePath, {
            destination: destinationPath,
            metadata: {
                contentType: 'text/plain',
            },
        });
        
        const fileSize = fs.statSync(localFilePath).size;
        const folderPath = path.posix.dirname(destinationPath);
        const fileUri = `gs://${bucketName}/${destinationPath}`;
        const folderUri = `gs://${bucketName}/${folderPath === "." ? "" : `${folderPath}/`}`;

        console.log(`✅ File uploaded to ${fileUri}`);
        console.log(`   Saved folder: ${folderUri}`);
        
        return {
            status: 'success',
            bucket: bucketName,
            folder: folderPath,
            filename: destinationPath,
            size_bytes: fileSize,
            url: fileUri
        };
        
    } catch (error) {
        console.error(`❌ Error uploading to GCS: ${error.message}`);
        console.error(`   Bucket: ${bucketName}`);
        throw error;
    }
}

/**
 * Upload JSON data directly to GCS
 * 
 * @param {Object} data - JavaScript object to save as JSON
 * @param {string} destinationPath - Destination path in GCS bucket
 * @returns {Promise<Object>} Upload status information
 */
async function uploadJSONToGCS(data, destinationPath) {
    const bucketName = process.env.GCS_BUCKET;
    
    if (!bucketName) {
        console.log('⚠️  GCS_BUCKET environment variable not set');
        console.log('⚠️  Skipping GCS upload');
        return { status: 'skipped', reason: 'GCS_BUCKET not set' };
    }

    try {
        // Initialize GCS client
        const storage = new Storage();
        const bucket = storage.bucket(bucketName);
        
        // Convert to JSON string
        const jsonPayload = JSON.stringify(data, null, 2);
        
        // Upload JSON
        const blob = bucket.file(destinationPath);
        await blob.save(jsonPayload, {
            contentType: 'application/json',
        });

        const folderPath = path.posix.dirname(destinationPath);
        const fileUri = `gs://${bucketName}/${destinationPath}`;
        const folderUri = `gs://${bucketName}/${folderPath === "." ? "" : `${folderPath}/`}`;

        console.log(`✅ JSON uploaded to ${fileUri}`);
        console.log(`   Saved folder: ${folderUri}`);
        
        return {
            status: 'success',
            bucket: bucketName,
            folder: folderPath,
            filename: destinationPath,
            size_bytes: Buffer.byteLength(jsonPayload, 'utf8'),
            url: fileUri
        };
        
    } catch (error) {
        console.error(`❌ Error uploading JSON to GCS: ${error.message}`);
        console.error(`   Bucket: ${bucketName}`);
        throw error;
    }
}

/**
 * Upload text content directly to GCS
 * 
 * @param {string} content - Text content to upload
 * @param {string} destinationPath - Destination path in GCS bucket
 * @returns {Promise<Object>} Upload status information
 */
async function uploadTextToGCS(content, destinationPath) {
    const bucketName = process.env.GCS_BUCKET;
    
    if (!bucketName) {
        console.log('⚠️  GCS_BUCKET environment variable not set');
        console.log('⚠️  Skipping GCS upload');
        return { status: 'skipped', reason: 'GCS_BUCKET not set' };
    }

    try {
        // Initialize GCS client
        const storage = new Storage();
        const bucket = storage.bucket(bucketName);
        
        // Upload text
        const blob = bucket.file(destinationPath);
        await blob.save(content, {
            contentType: 'text/plain',
        });

        const folderPath = path.posix.dirname(destinationPath);
        const fileUri = `gs://${bucketName}/${destinationPath}`;
        const folderUri = `gs://${bucketName}/${folderPath === "." ? "" : `${folderPath}/`}`;

        console.log(`✅ Text uploaded to ${fileUri}`);
        console.log(`   Saved folder: ${folderUri}`);
        
        return {
            status: 'success',
            bucket: bucketName,
            folder: folderPath,
            filename: destinationPath,
            size_bytes: Buffer.byteLength(content, 'utf8'),
            url: fileUri
        };
        
    } catch (error) {
        console.error(`❌ Error uploading text to GCS: ${error.message}`);
        console.error(`   Bucket: ${bucketName}`);
        throw error;
    }
}

module.exports = {
    uploadFileToGCS,
    uploadJSONToGCS,
    uploadTextToGCS
};
