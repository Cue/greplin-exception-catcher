/*
 * Copyright 2011 The greplin-exception-catcher Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#import "GecErrorReporter.h"
#import "JSON.h" // From http://stig.github.com/json-framework/

static GecErrorReporter * sharedInstance = nil;
static NSMutableDictionary * uploadMap = nil;

@interface UploadDelegate : NSObject {
    NSString * _filename;        
}

- (id)initWithFilename:(NSString*)filename;    

@end


@implementation GecErrorReporter

@synthesize serverAddress;
@synthesize secret;
@synthesize environment;
@synthesize project;
@synthesize itemLimit;

+ (GecErrorReporter *)sharedInstance {
    if (sharedInstance == nil) {
        sharedInstance = [[GecErrorReporter alloc] init];
    }
    return sharedInstance;
}

+ (NSString *)crashFileDir {
    NSArray * paths = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES);
    NSString * path = [paths objectAtIndex:0];
    return [path stringByAppendingPathComponent:@"gec"];
}

+ (NSString *)crashFilePath {
    NSTimeInterval timestamp = [[NSDate date] timeIntervalSince1970];
    NSString * pathString = [[self crashFileDir] stringByAppendingFormat:@"/crash_%d.gec",timestamp];
                    
    return pathString;
}

+ (void)initialize {    
    uploadMap = [[NSMutableDictionary alloc] init];
    
    NSString * crashDir = [self crashFileDir];
    
    NSFileManager * fm = [NSFileManager defaultManager];
    if (![fm fileExistsAtPath:crashDir isDirectory:NULL]) {
        [fm createDirectoryAtPath:crashDir withIntermediateDirectories:YES attributes:nil error:NULL];
    }
}

- (id)init {
    self = [super init];
    if (self) {
        //Nothing for now.
    }
    return self;
}

- (void)reportError:(NSException *)exception andMessage:(NSString *)message {
    @try {
        @throw exception;
    }
    @catch (NSException *exception_) {
        NSMutableDictionary *result = [NSMutableDictionary dictionaryWithCapacity:7];
        [result setObject:project forKey:@"project"];
        [result setObject:environment forKey:@"environment"];
        [result setObject:[UIDevice currentDevice].model forKey:@"serverName"];
        [result setObject:[exception_ name] forKey:@"type"];
        [result setObject:[exception_ reason] forKey:@"message"];
        [result setObject:message forKey:@"logMessage"];
        [result setObject:[NSNumber numberWithInt:(int)[[NSDate date] timeIntervalSince1970]] forKey:@"timestamp"];
        
        [result setObject:[[exception_ callStackSymbols] componentsJoinedByString:@"\n"] forKey:@"backtrace"];
        
        NSData *jsonData = [[result JSONRepresentation] dataUsingEncoding:NSUTF8StringEncoding];
        [jsonData writeToFile:[GecErrorReporter crashFilePath] atomically:YES];
        
        [self syncErrors];        
    }
}


- (void)uploadError:(NSString*)filename {
    
    UploadDelegate * delegate = [uploadMap objectForKey:filename];
    
    //We don't want multiple uploaders of the same file.
    if (nil!=delegate) {
        return;
    }
    
    delegate = [[UploadDelegate alloc] initWithFilename:filename];
    [uploadMap setObject:delegate forKey:filename];
    [delegate release];
    
    NSString *path = [@"report?key=" stringByAppendingString:secret];
    NSURL *url = [NSURL URLWithString:path relativeToURL:serverAddress];
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
    [request setHTTPMethod:@"POST"];
    [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
    [request setHTTPBody:[NSData dataWithContentsOfFile:filename]];
    
    [[NSURLConnection alloc] initWithRequest:request delegate:delegate];
}

- (void)pruneError:(NSString*)filename {
    
    //Don't delete a file from under the uploader
    if (nil!=[uploadMap objectForKey:filename]) {
        return;
    }
    
    NSLog(@"Giving up on error file %@. Deleting", filename);
    [[NSFileManager defaultManager] removeItemAtPath:filename error:NULL];    
}


// We can either attempt to upload the error, or if enough have piled up due to failure, 
// just start deleting according to itemLimit. 

// Since sorting by date in NSFileManager is kind of a pain, we're just doing it in unmodified order. 
// If there's enough demand to do FIFO, it could be added.

- (void)handleErrorFile:(NSString*)filename atIndex:(NSInteger)itemCount {    
    NSString * fullname = [[GecErrorReporter crashFileDir] stringByAppendingPathComponent:filename];    
    if (itemLimit && itemCount > itemLimit) {
        [self pruneError:fullname];
    } else {
        [self uploadError:fullname];         
    }
}

- (void)syncErrors {
    NSString* dir = [GecErrorReporter crashFileDir];
    NSError* error = nil;
	
    NSArray* files = [[NSFileManager defaultManager] contentsOfDirectoryAtPath:dir
                                                                         error:&error];
    
    NSInteger itemCount = 0;
    for (NSString * filename in files) {
        if ([filename hasSuffix:@".gec"]) {
            [self handleErrorFile:filename atIndex:itemCount++];
        }
    }
}

- (void)dealloc {
    [serverAddress release];
    [secret release];
    [environment release];
    [project release];
    [super dealloc];
}

@end

@implementation UploadDelegate

- (id)initWithFilename:(NSString *)filename {
    self = [super init];
    if (self) {
        _filename = [filename retain];
    }
    return self;
}

- (void)deleteCrashFile {
    [[NSFileManager defaultManager] removeItemAtPath:_filename error:NULL];   
}

- (void)connectionDidFinishLoading:(NSURLConnection *)connection {
    NSLog(@"Successfully uploaded exception for file: %@", _filename);
    [self deleteCrashFile];
    
    [uploadMap removeObjectForKey:_filename];
    [connection release];
}

- (void)connection:(NSURLConnection *)connection didFailWithError:(NSError *)error {
    NSLog(@"Failed to upload exception: %@", error);
    
    [uploadMap removeObjectForKey:_filename];
    [connection release];
}

- (void)dealloc {
    [_filename release];
    [super dealloc];
}

@end
