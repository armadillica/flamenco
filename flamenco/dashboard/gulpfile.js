var gulp          = require('gulp'),
    plumber       = require('gulp-plumber'),
    sass          = require('gulp-sass'),
    sourcemaps    = require('gulp-sourcemaps'),
    autoprefixer  = require('gulp-autoprefixer'),
    jade          = require('gulp-jade'),
    livereload    = require('gulp-livereload');


/* CSS */
gulp.task('styles', function() {
    gulp.src('src/styles/**/*.sass')
        .pipe(plumber())
        .pipe(sourcemaps.init())
        .pipe(sass({
            outputStyle: 'compressed'}
            ))
        .pipe(autoprefixer("last 3 version", "safari 5", "ie 8", "ie 9"))
        .pipe(sourcemaps.write('.'))
        .pipe(gulp.dest('application/static/css'))
        .pipe(livereload());
});


/* Templates - Jade */
gulp.task('templates', function() {
    gulp.src('src/templates/**/*.jade')
        .pipe(jade({
            pretty: false
        }))
        .pipe(gulp.dest('application/templates/'))
        .pipe(livereload());
});


// While developing, run 'gulp watch'
gulp.task('watch',function() {
    livereload.listen();

    gulp.watch('src/styles/**/*.sass',['styles']);
    gulp.watch('src/templates/**/*.jade',['templates']);
});


// Run 'gulp' to build everything at once
gulp.task('default', ['styles', 'templates']);
